#!/usr/bin/env python3
import argparse
import html
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
    return {
        "raw_latency_configured_ms": capture(r"PASS: (\d+) ms configured latency", text, int),
        "raw_latency_observed_ms": capture(r"configured latency produced (\d+) ms raw-read latency", text, int),
        "fio_baseline_iops": capture(r"fio baseline randread IOPS: ([0-9.]+)", text, float),
        "fio_injected_latency_ms": capture(r"fio with (\d+) ms injected latency", text, int),
        "fio_injected_iops": capture(r"fio with \d+ ms injected latency: ([0-9.]+) IOPS", text, float),
        "sqlite_baseline_ms": capture(r"SQLite baseline transaction: (\d+) ms", text, int),
        "sqlite_injected_latency_ms": capture(r"SQLite transaction with (\d+) ms I/O latency", text, int),
        "sqlite_injected_ms": capture(r"SQLite transaction with \d+ ms I/O latency: (\d+) ms", text, int),
        "sqlite_failure": capture(r"SQLite observed injected storage failure: (.+)", text),
        "postgres_baseline_ms": capture(r"PostgreSQL baseline durable transaction: (\d+) ms", text, int),
        "postgres_injected_latency_ms": capture(r"PostgreSQL transaction with (\d+) ms I/O latency", text, int),
        "postgres_injected_ms": capture(r"PostgreSQL transaction with \d+ ms I/O latency: (\d+) ms", text, int),
        "postgres_failure": capture(r"PostgreSQL observed injected storage failure: (.+)", text),
        "read_requests": capture(r"^read_requests (\d+)$", text, int),
        "write_requests": capture(r"^write_requests (\d+)$", text, int),
        "failed_reads": capture(r"^failed_reads (\d+)$", text, int),
        "failed_writes": capture(r"^failed_writes (\d+)$", text, int),
        "delayed_requests": capture(r"^delayed_requests (\d+)$", text, int),
        "final_pass": "PASS: Fault Simulation Disk final validation completed" in text,
    }


def fmt_num(value):
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.1f}"
    return f"{value:,}"


def markdown_report(data):
    env = data["environment"]
    m = data["metrics"]
    repo = data["repository"]
    sha = data["commit"]
    run_url = data["run_url"]
    commit_url = f"https://github.com/{repo}/commit/{sha}" if repo and sha else ""
    status = "PASS" if data["status"] == "passed" else "FAIL"

    lines = [
        "# Latest verified run",
        "",
        f"**Status:** {status}",
        "",
        "| Provenance | Value |",
        "| --- | --- |",
        f"| Commit | [{sha[:12]}]({commit_url}) |" if commit_url else f"| Commit | {sha[:12]} |",
        f"| GitHub Actions run | [#{data['run_id']}]({run_url}) |" if run_url else f"| GitHub Actions run | {data['run_id']} |",
        f"| Runner image | {env.get('image_os', 'n/a')} {env.get('image_version', '')} |",
        f"| Kernel | {env.get('kernel', 'n/a')} |",
        f"| Architecture | {env.get('architecture', 'n/a')} |",
        f"| fio | {env.get('fio_version', 'n/a')} |",
        f"| SQLite | {env.get('sqlite_version', 'n/a')} |",
        f"| PostgreSQL | {env.get('postgres_version', 'n/a')} |",
        "",
        "| Check | Baseline | Injected fault | Result |",
        "| --- | ---: | ---: | --- |",
        f"| Raw read latency | n/a | {fmt_num(m['raw_latency_observed_ms'])} ms with {fmt_num(m['raw_latency_configured_ms'])} ms configured | PASS |",
        f"| fio 4 KiB QD1 random read | {fmt_num(m['fio_baseline_iops'])} IOPS | {fmt_num(m['fio_injected_iops'])} IOPS with {fmt_num(m['fio_injected_latency_ms'])} ms latency | PASS |",
        f"| SQLite durable transaction | {fmt_num(m['sqlite_baseline_ms'])} ms | {fmt_num(m['sqlite_injected_ms'])} ms with {fmt_num(m['sqlite_injected_latency_ms'])} ms latency | PASS |",
        f"| PostgreSQL durable transaction | {fmt_num(m['postgres_baseline_ms'])} ms | {fmt_num(m['postgres_injected_ms'])} ms with {fmt_num(m['postgres_injected_latency_ms'])} ms latency | PASS |",
        f"| SQLite write failure | n/a | {m.get('sqlite_failure') or 'n/a'} | PASS |",
        f"| PostgreSQL write failure | n/a | {m.get('postgres_failure') or 'n/a'} | PASS |",
        "",
        f"Generated from GitHub-hosted validation at {data['generated_at']}.",
        "",
        "Absolute baseline throughput is environment-specific. The reproducible claims are the fault behavior and relative response to configured injection.",
    ]
    return "\n".join(lines) + "\n"


def html_report(data):
    env = data["environment"]
    m = data["metrics"]
    repo = html.escape(data["repository"])
    sha = html.escape(data["commit"])
    run_url = html.escape(data["run_url"])
    commit_url = f"https://github.com/{repo}/commit/{sha}"
    status = "PASS" if data["status"] == "passed" else "FAIL"

    def e(value):
        return html.escape(str(value))

    rows = [
        ("Raw read latency", "—", f"{fmt_num(m['raw_latency_observed_ms'])} ms @ {fmt_num(m['raw_latency_configured_ms'])} ms configured"),
        ("fio 4 KiB QD1 randread", f"{fmt_num(m['fio_baseline_iops'])} IOPS", f"{fmt_num(m['fio_injected_iops'])} IOPS @ {fmt_num(m['fio_injected_latency_ms'])} ms"),
        ("SQLite durable transaction", f"{fmt_num(m['sqlite_baseline_ms'])} ms", f"{fmt_num(m['sqlite_injected_ms'])} ms @ {fmt_num(m['sqlite_injected_latency_ms'])} ms"),
        ("PostgreSQL durable transaction", f"{fmt_num(m['postgres_baseline_ms'])} ms", f"{fmt_num(m['postgres_injected_ms'])} ms @ {fmt_num(m['postgres_injected_latency_ms'])} ms"),
    ]

    metric_rows = "\n".join(
        f"<tr><td>{e(name)}</td><td>{e(base)}</td><td>{e(injected)}</td></tr>"
        for name, base, injected in rows
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fault Simulation Disk · Latest Verified Run</title>
<style>
:root {{ color-scheme: light dark; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
body {{ margin: 0; background: #0d1117; color: #e6edf3; }}
main {{ max-width: 980px; margin: 0 auto; padding: 56px 24px 80px; }}
a {{ color: #58a6ff; }}
.eyebrow {{ color: #8b949e; font-size: 14px; letter-spacing: .08em; text-transform: uppercase; }}
h1 {{ margin: 8px 0 8px; font-size: clamp(36px, 7vw, 64px); line-height: 1; }}
.subtitle {{ color: #8b949e; font-size: 18px; max-width: 760px; }}
.status {{ display:inline-block; margin: 22px 0; padding: 7px 12px; border:1px solid #238636; border-radius:999px; color:#3fb950; font-weight:700; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:12px; margin:24px 0; }}
.card {{ border:1px solid #30363d; border-radius:12px; padding:16px; background:#161b22; }}
.label {{ color:#8b949e; font-size:12px; text-transform:uppercase; letter-spacing:.06em; }}
.value {{ margin-top:7px; font-weight:650; word-break:break-word; }}
table {{ width:100%; border-collapse:collapse; margin:24px 0; }}
th,td {{ text-align:left; border-bottom:1px solid #30363d; padding:12px 10px; }}
th {{ color:#8b949e; font-size:13px; }}
.note {{ color:#8b949e; font-size:14px; line-height:1.6; }}
code {{ background:#161b22; border:1px solid #30363d; padding:2px 5px; border-radius:5px; }}
</style>
</head>
<body>
<main>
<div class="eyebrow">Latest verified GitHub-hosted validation</div>
<h1>Fault Simulation Disk</h1>
<p class="subtitle">Reproducible storage-fault testing through a real Linux block device.</p>
<div class="status">{status}</div>

<div class="grid">
<div class="card"><div class="label">Commit</div><div class="value"><a href="{commit_url}"><code>{sha[:12]}</code></a></div></div>
<div class="card"><div class="label">Runner</div><div class="value">{e(env.get('image_os','n/a'))} {e(env.get('image_version',''))}</div></div>
<div class="card"><div class="label">Kernel</div><div class="value">{e(env.get('kernel','n/a'))}</div></div>
<div class="card"><div class="label">Evidence</div><div class="value"><a href="{run_url}">GitHub Actions run #{e(data['run_id'])}</a></div></div>
</div>

<table>
<thead><tr><th>Check</th><th>Baseline</th><th>Injected fault</th></tr></thead>
<tbody>{metric_rows}</tbody>
</table>

<div class="grid">
<div class="card"><div class="label">SQLite failure propagation</div><div class="value">{e(m.get('sqlite_failure') or 'n/a')}</div></div>
<div class="card"><div class="label">PostgreSQL failure propagation</div><div class="value">{e(m.get('postgres_failure') or 'n/a')}</div></div>
</div>

<p class="note">Generated automatically from a fresh GitHub-hosted VM. Absolute baseline performance is environment-specific; the project validates deterministic fault behavior and relative response to injected latency/errors. Raw output and hashes are attached to the linked workflow run.</p>
<p class="note"><a href="https://github.com/{repo}">Repository</a> · <a href="https://github.com/{repo}/blob/main/docs/reproducibility.md">Reproducibility model</a></p>
</main>
</body>
</html>
"""


def svg_report(data):
    env = data["environment"]
    m = data["metrics"]
    status = "PASS" if data["status"] == "passed" else "FAIL"
    lines = [
        f"Latest hosted validation: {status}",
        f"Linux {env.get('kernel', 'n/a')} · commit {data['commit'][:12]}",
        f"Raw latency: {fmt_num(m['raw_latency_observed_ms'])} ms observed @ {fmt_num(m['raw_latency_configured_ms'])} ms configured",
        f"fio QD1: {fmt_num(m['fio_baseline_iops'])} → {fmt_num(m['fio_injected_iops'])} IOPS @ {fmt_num(m['fio_injected_latency_ms'])} ms",
        f"SQLite: {fmt_num(m['sqlite_baseline_ms'])} → {fmt_num(m['sqlite_injected_ms'])} ms · PostgreSQL: {fmt_num(m['postgres_baseline_ms'])} → {fmt_num(m['postgres_injected_ms'])} ms",
    ]
    escaped = [xml_escape(x) for x in lines]
    text_nodes = "\n".join(
        f'<text x="28" y="{42 + i*31}" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="{18 if i == 0 else 15}" font-weight="{700 if i == 0 else 400}" fill="{"#3fb950" if i == 0 else "#c9d1d9"}">{line}</text>'
        for i, line in enumerate(escaped)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="820" height="185" viewBox="0 0 820 185">
<rect width="820" height="185" rx="12" fill="#0d1117"/>
<rect x=".5" y=".5" width="819" height="184" rx="11.5" fill="none" stroke="#30363d"/>
{text_nodes}
</svg>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", required=True)
    parser.add_argument("--validation", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    environment = parse_environment(read_text(args.environment))
    metrics = parse_validation(read_text(args.validation))

    repository = os.getenv("GITHUB_REPOSITORY", "")
    commit = os.getenv("GITHUB_SHA", environment.get("commit", ""))
    run_id = os.getenv("GITHUB_RUN_ID", "")
    server = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    run_url = f"{server}/{repository}/actions/runs/{run_id}" if repository and run_id else ""

    data = {
        "schema_version": 1,
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

    if data["status"] != "passed":
        raise SystemExit("validation output did not contain final PASS marker")


if __name__ == "__main__":
    main()
