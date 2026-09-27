#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for cmd in fio sqlite3 python3 mkfs.ext4 pg_config; do
	command -v "$cmd" >/dev/null || {
		echo "Missing dependency: $cmd" >&2
		echo "Install with: sudo apt install fio sqlite3 python3 e2fsprogs postgresql postgresql-client util-linux" >&2
		exit 1
	}
done

"$ROOT/scripts/dev.sh" smoke
"$ROOT/scripts/dev.sh" fault-test
"$ROOT/scripts/dev.sh" stats-test
"$ROOT/scripts/dev.sh" fio-test
"$ROOT/scripts/dev.sh" sqlite-test
"$ROOT/scripts/dev.sh" postgres-test

echo
echo "PASS: Fault Simulation Disk final validation completed"
echo
"$ROOT/scripts/dev.sh" stats
