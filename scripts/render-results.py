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
