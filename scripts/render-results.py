#!/usr/bin/env python3
import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def parse_environment(text):
    env = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            if re.fullmatch(r"[a-zA-Z0-9_]+", key):
                env[key] = value.strip()
    return env


def capture(pattern, text, cast=str, default=None):
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        return default
    return cast(match.group(1))


def parse_validation(text):
    has = lambda marker: marker in text
    return {
        "ext4_pass": has("PASS: formatted, mounted, wrote, synced, and read back through /dev/faultsim0"),
        "block_ops_advertised_pass": has("PASS: block queue advertises discard and write-zeroes support"),
        "discard_pass": has("PASS: discard zeroed the requested range"),
        "write_zeroes_pass": has("PASS: write-zeroes zeroed the requested range"),
        "raw_latency_configured_ms": capture(r"PASS: (\d+) ms configured latency", text, int),
        "raw_latency_observed_ms": capture(r"configured latency produced (\d+) ms raw-read latency", text, int),
        "raw_write_failure": capture(r"Raw write observed injected failure: (.+)", text),
        "raw_write_failure_pass": has("PASS: write_fail_pct=100 rejected a raw write"),
        "raw_read_failure": capture(r"Raw read observed injected failure: (.+)", text),
        "raw_read_failure_pass": has("PASS: read_fail_pct=100 rejected a raw read"),
        "stats_pass": has("PASS: runtime statistics checks completed"),
        "fio_baseline_iops": capture(r"fio baseline randread IOPS: ([0-9.]+)", text, float),
        "fio_injected_latency_ms": capture(r"fio with (\d+) ms injected latency", text, int),
        "fio_injected_iops": capture(r"fio with \d+ ms injected latency: ([0-9.]+) IOPS", text, float),
        "fio_pass": has("PASS: fio measured the expected performance impact from injected latency"),
        "sqlite_baseline_ms": capture(r"SQLite baseline transaction: (\d+) ms", text, int),
        "sqlite_injected_latency_ms": capture(r"SQLite transaction with (\d+) ms I/O latency", text, int),
        "sqlite_injected_ms": capture(r"SQLite transaction with \d+ ms I/O latency: (\d+) ms", text, int),
        "sqlite_latency_pass": has("PASS: SQLite transaction slowed under injected storage latency"),
        "sqlite_failure": capture(r"SQLite observed injected storage failure: (.+)", text),
        "sqlite_failure_pass": has("PASS: SQLite surfaced the injected block-device write failure"),
        "postgres_baseline_ms": capture(r"PostgreSQL baseline synchronous commit: (\d+) ms", text, int),
        "postgres_injected_latency_ms": capture(r"PostgreSQL transaction with (\d+) ms I/O latency", text, int),
        "postgres_injected_ms": capture(r"PostgreSQL transaction with \d+ ms I/O latency: (\d+) ms", text, int),
        "postgres_latency_pass": has("PASS: PostgreSQL synchronous commit slowed under injected storage latency"),
        "postgres_failure": capture(r"PostgreSQL observed injected storage failure: (.+)", text),
        "postgres_failure_pass": has("PASS: PostgreSQL surfaced the injected block-device write failure"),
        "read_requests": capture(r"^read_requests (\d+)$", text, int),
        "write_requests": capture(r"^write_requests (\d+)$", text, int),
        "read_bytes": capture(r"^read_bytes (\d+)$", text, int),
        "write_bytes": capture(r"^write_bytes (\d+)$", text, int),
        "failed_reads": capture(r"^failed_reads (\d+)$", text, int),
        "failed_writes": capture(r"^failed_writes (\d+)$", text, int),
        "delayed_requests": capture(r"^delayed_requests (\d+)$", text, int),
        "final_pass": has("PASS: Fault Simulation Disk final validation completed"),
    }


def fmt_num(value):
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.1f}"
    return f"{value:,}"


def pass_text(value):
    return "PASS" if value else "FAIL"


def compact_failure(value, limit=82):
    if not value:
        return "n/a"
    value = re.sub(r"\s+", " ", value.strip())
    if len(value) <= limit:
        return value
    if "Input/output error" in value:
        prefix = value.split("Input/output error", 1)[0]
        prefix = prefix[: max(0, limit - len("… Input/output error"))].rstrip()
        return f"{prefix}… Input/output error"
    return value[: limit - 1].rstrip() + "…"


def sqlite_failure_lines(value):
    value = value or ""
    if "disk I/O error (10)" in value:
        return ["disk I/O error (10)"]
    return [compact_failure(value, 26)]


def postgres_failure_lines(value):
    value = value or ""
    lines = []
    severity = value.split(":", 1)[0].strip() if ":" in value else ""
    if "fdatasync" in value:
        lines.append(f"{severity + ': ' if severity else ''}fdatasync failed")
    if "Input/output error" in value:
        lines.append("Input/output error")
    if not lines:
        lines.append(compact_failure(value, 28))
    return lines[:2]


def markdown_report(data):
    env = data["environment"]
    m = data["metrics"]
    repo = data["repository"]
    sha = data["commit"]
    run_url = data["run_url"]
    commit_url = f"https://github.com/{repo}/commit/{sha}" if repo and sha else ""
    status = "PASS" if data["status"] == "passed" else "FAIL"

    lines = [
        "# Fault Simulation Disk test results",
        "",
        f"**Overall status: {status}**",
        "",
        "Generated from the validation output for the commit and GitHub Actions run below.",
        "",
        "## What happened",
        "",
        "| Scenario | Fault injected | What the workload observed | Status |",
        "| --- | --- | --- | --- |",
        f"| ext4 filesystem | None | Format → mount → write → sync → read back | {pass_text(m['ext4_pass'])} |",
        f"| DISCARD / WRITE_ZEROES | None | Queue advertises both operations and both ranges read back as zero | {pass_text(m['block_ops_advertised_pass'] and m['discard_pass'] and m['write_zeroes_pass'])} |",
        f"| Raw block read | +{fmt_num(m['raw_latency_configured_ms'])} ms latency | {fmt_num(m['raw_latency_observed_ms'])} ms end-to-end read latency | {pass_text(m['raw_latency_observed_ms'] is not None)} |",
        f"| Raw block read | 100% read failure | `{m.get('raw_read_failure') or 'n/a'}` | {pass_text(m['raw_read_failure_pass'])} |",
        f"| Raw block write | 100% write failure | `{m.get('raw_write_failure') or 'n/a'}` | {pass_text(m['raw_write_failure_pass'])} |",
        f"| fio 4 KiB QD1 random read | +{fmt_num(m['fio_injected_latency_ms'])} ms latency | {fmt_num(m['fio_baseline_iops'])} → {fmt_num(m['fio_injected_iops'])} IOPS | {pass_text(m['fio_pass'])} |",
        f"| SQLite FULL-sync transaction | +{fmt_num(m['sqlite_injected_latency_ms'])} ms latency | {fmt_num(m['sqlite_baseline_ms'])} → {fmt_num(m['sqlite_injected_ms'])} ms | {pass_text(m['sqlite_latency_pass'])} |",
        f"| SQLite FULL-sync transaction | 100% write failure | `{m.get('sqlite_failure') or 'n/a'}` | {pass_text(m['sqlite_failure_pass'])} |",
        f"| PostgreSQL synchronous commit | +{fmt_num(m['postgres_injected_latency_ms'])} ms latency | {fmt_num(m['postgres_baseline_ms'])} → {fmt_num(m['postgres_injected_ms'])} ms | {pass_text(m['postgres_latency_pass'])} |",
        f"| PostgreSQL synchronous commit | 100% write failure | `{m.get('postgres_failure') or 'n/a'}` | {pass_text(m['postgres_failure_pass'])} |",
        f"| debugfs accounting | Mixed workload | Requests, bytes, failures, and delayed I/O recorded | {pass_text(m['stats_pass'])} |",
        "",
        "## Provenance",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Commit | [{sha[:12]}]({commit_url}) |" if commit_url else f"| Commit | {sha[:12]} |",
        f"| GitHub Actions run | [#{data['run_id']}]({run_url}) |" if run_url else f"| GitHub Actions run | {data['run_id']} |",
        f"| Runner | {env.get('image_os', 'n/a')} {env.get('image_version', '')} |",
        f"| Kernel | {env.get('kernel', 'n/a')} |",
        f"| Architecture | {env.get('architecture', 'n/a')} |",
        f"| fio | {env.get('fio_version', 'n/a')} |",
        f"| SQLite | {env.get('sqlite_version', 'n/a')} |",
        f"| PostgreSQL | {env.get('postgres_version', 'n/a')} |",
        "",
        f"Generated at {data['generated_at']}. Performance measurements depend on the runner and kernel listed above.",
    ]
    return "\n".join(lines) + "\n"


def svg_text(x, y, text, size=15, weight=400, fill="#c9d1d9"):
    return (
        f'<text x="{x}" y="{y}" font-family="ui-sans-serif, -apple-system, BlinkMacSystemFont, '
        f'\'Segoe UI\', sans-serif" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}">{xml_escape(str(text))}</text>'
    )


def svg_mono(x, y, text, size=14, weight=400, fill="#c9d1d9"):
    return (
        f'<text x="{x}" y="{y}" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">{xml_escape(str(text))}</text>'
    )


def svg_card(x, y, width, height, title, fault, observed, status="PASS", mono=False):
    nodes = [
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="10" fill="#161b22" stroke="#30363d"/>',
        svg_text(x + 18, y + 28, title, 15, 700, "#f0f6fc"),
        svg_text(x + width - 62, y + 28, status, 12, 700, "#3fb950" if status == "PASS" else "#f85149"),
        svg_text(x + 18, y + 53, fault, 12, 600, "#8b949e"),
        (svg_mono if mono else svg_text)(x + 18, y + 79, observed, 14, 500, "#c9d1d9"),
    ]
    return "\n".join(nodes)


def svg_error_card(x, y, width, title, fault, lines, status="PASS"):
    nodes = [
        f'<rect x="{x}" y="{y}" width="{width}" height="108" rx="10" fill="#161b22" stroke="#30363d"/>',
        svg_text(x + 18, y + 28, title, 15, 700, "#f0f6fc"),
        svg_text(x + width - 62, y + 28, status, 12, 700, "#3fb950" if status == "PASS" else "#f85149"),
        svg_text(x + 18, y + 53, fault, 12, 600, "#8b949e"),
    ]
    for i, line in enumerate(lines[:2]):
        nodes.append(svg_mono(x + 18, y + 77 + i * 19, line, 12, 500, "#c9d1d9"))
    return "\n".join(nodes)


def svg_report(data):
    env = data["environment"]
    m = data["metrics"]
    status = "PASS" if data["status"] == "passed" else "FAIL"
    width = 1000
    height = 650
    nodes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" rx="14" fill="#0d1117"/>',
        f'<rect x=".5" y=".5" width="{width-1}" height="{height-1}" rx="13.5" fill="none" stroke="#30363d"/>',
        svg_text(28, 42, "TEST RESULTS", 13, 700, "#8b949e"),
        svg_text(28, 75, "Fault Simulation Disk", 27, 700, "#f0f6fc"),
        svg_text(28, 102, "Storage latency and I/O errors tested with ext4, fio, SQLite and PostgreSQL.", 15, 400, "#8b949e"),
        svg_text(897, 75, status, 18, 700, "#3fb950" if status == "PASS" else "#f85149"),
        svg_text(28, 135, f"Linux {env.get('kernel', 'n/a')}  •  commit {data['commit'][:12]}  •  Actions #{data['run_id']}", 13, 400, "#8b949e"),
        svg_text(28, 174, "1  NORMAL BLOCK DEVICE", 13, 700, "#58a6ff"),
        svg_card(28, 190, 460, 94, "ext4 filesystem", "NO FAULT", "format → mount → write → sync → read back", pass_text(m["ext4_pass"])),
        svg_card(500, 190, 472, 94, "DISCARD / WRITE_ZEROES", "QUEUE-ADVERTISED", "both test ranges read back as zero", pass_text(m["block_ops_advertised_pass"] and m["discard_pass"] and m["write_zeroes_pass"])),
        svg_text(28, 318, "2  LATENCY PROPAGATION", 13, 700, "#58a6ff"),
        svg_card(28, 334, 220, 98, "Raw read", f"+{fmt_num(m['raw_latency_configured_ms'])} ms", f"{fmt_num(m['raw_latency_observed_ms'])} ms observed"),
        svg_card(260, 334, 220, 98, "fio", f"+{fmt_num(m['fio_injected_latency_ms'])} ms", f"{fmt_num(m['fio_baseline_iops'])} → {fmt_num(m['fio_injected_iops'])} IOPS"),
        svg_card(492, 334, 220, 98, "SQLite", f"+{fmt_num(m['sqlite_injected_latency_ms'])} ms", f"{fmt_num(m['sqlite_baseline_ms'])} → {fmt_num(m['sqlite_injected_ms'])} ms"),
        svg_card(724, 334, 248, 98, "PostgreSQL", f"+{fmt_num(m['postgres_injected_latency_ms'])} ms", f"{fmt_num(m['postgres_baseline_ms'])} → {fmt_num(m['postgres_injected_ms'])} ms"),
        svg_text(28, 466, "3  I/O ERROR PROPAGATION", 13, 700, "#58a6ff"),
        svg_error_card(28, 482, 220, "Raw read", "100% READ FAIL", ["userspace observed", "Input/output error" if "Input/output error" in (m.get("raw_read_failure") or "") else compact_failure(m.get("raw_read_failure"), 22)], pass_text(m["raw_read_failure_pass"])),
        svg_error_card(260, 482, 220, "Raw write", "100% WRITE FAIL", ["userspace observed", "Input/output error" if "Input/output error" in (m.get("raw_write_failure") or "") else compact_failure(m.get("raw_write_failure"), 22)], pass_text(m["raw_write_failure_pass"])),
        svg_error_card(492, 482, 220, "SQLite", "100% WRITE FAIL", sqlite_failure_lines(m.get("sqlite_failure")), pass_text(m["sqlite_failure_pass"])),
        svg_error_card(724, 482, 248, "PostgreSQL", "100% WRITE FAIL", postgres_failure_lines(m.get("postgres_failure")), pass_text(m["postgres_failure_pass"])),
        svg_text(28, 616, "Generated by GitHub Actions. See the report for raw output and environment details.", 12, 400, "#8b949e"),
        "</svg>",
    ]
    return "\n".join(nodes) + "\n"


def validate_parsed_results(metrics):
    required_true = [
        "ext4_pass",
        "block_ops_advertised_pass",
        "discard_pass",
        "write_zeroes_pass",
        "raw_read_failure_pass",
        "raw_write_failure_pass",
        "stats_pass",
        "fio_pass",
        "sqlite_latency_pass",
        "sqlite_failure_pass",
        "postgres_latency_pass",
        "postgres_failure_pass",
        "final_pass",
    ]
    missing_pass = [name for name in required_true if not metrics.get(name)]

    required_values = [
        "raw_latency_configured_ms",
        "raw_latency_observed_ms",
        "raw_read_failure",
        "raw_write_failure",
        "fio_baseline_iops",
        "fio_injected_latency_ms",
        "fio_injected_iops",
        "sqlite_baseline_ms",
        "sqlite_injected_latency_ms",
        "sqlite_injected_ms",
        "sqlite_failure",
        "postgres_baseline_ms",
        "postgres_injected_latency_ms",
        "postgres_injected_ms",
        "postgres_failure",
    ]
    missing_values = [name for name in required_values if metrics.get(name) is None]

    if missing_pass or missing_values:
        details = []
        if missing_pass:
            details.append("missing PASS markers: " + ", ".join(missing_pass))
        if missing_values:
            details.append("missing parsed values: " + ", ".join(missing_values))
        raise SystemExit("validation report is incomplete: " + ". ".join(details))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", required=True)
    parser.add_argument("--validation", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    environment = parse_environment(read_text(args.environment))
    metrics = parse_validation(read_text(args.validation))
    validate_parsed_results(metrics)

    repository = os.getenv("GITHUB_REPOSITORY", "")
    commit = os.getenv("GITHUB_SHA", environment.get("commit", ""))
    run_id = os.getenv("GITHUB_RUN_ID", "")
    server = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    run_url = f"{server}/{repository}/actions/runs/{run_id}" if repository and run_id else ""

    data = {
        "schema_version": 2,
        "status": "passed" if metrics["final_pass"] else "failed",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "repository": repository,
        "commit": commit,
        "run_id": run_id,
        "run_url": run_url,
        "environment": environment,
        "metrics": metrics,
    }

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    (out / "latest.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    md = markdown_report(data)
    (out / "latest.md").write_text(md, encoding="utf-8")
    (out / "README.md").write_text(md, encoding="utf-8")
    (out / "latest.svg").write_text(svg_report(data), encoding="utf-8")

    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write(md)


if __name__ == "__main__":
    main()
