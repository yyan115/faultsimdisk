#!/usr/bin/env bash
set -euo pipefail

DEVICE=/dev/faultsim0
PARAMS=/sys/module/faultsimdisk/parameters
MOUNT_DIR=$(mktemp -d /tmp/faultsimdisk-sqlite.XXXXXX)
DB="$MOUNT_DIR/test.db"
mounted=0

reset_faults() {
	printf '0\n' > "$PARAMS/latency_ms" 2>/dev/null || true
	printf '0\n' > "$PARAMS/read_fail_pct" 2>/dev/null || true
	printf '0\n' > "$PARAMS/write_fail_pct" 2>/dev/null || true
}

cleanup() {
	reset_faults
	if (( mounted )); then
		sync || true
		umount "$MOUNT_DIR" 2>/dev/null || true
	fi
	rmdir "$MOUNT_DIR" 2>/dev/null || true
}
trap cleanup EXIT

if (( EUID != 0 )); then
	echo "Run through: ./scripts/dev.sh sqlite-test" >&2
	exit 1
fi

command -v sqlite3 >/dev/null || { echo "Missing sqlite3. Install: sudo apt install sqlite3" >&2; exit 1; }
test -b "$DEVICE" || { echo "$DEVICE is not a block device." >&2; exit 1; }

if findmnt -rn -S "$DEVICE" >/dev/null; then
	echo "$DEVICE is already mounted." >&2
	exit 1
fi

reset_faults
mkfs.ext4 -q -F "$DEVICE"
mount "$DEVICE" "$MOUNT_DIR"
mounted=1

sqlite3 "$DB" <<'SQL'
PRAGMA journal_mode=DELETE;
PRAGMA synchronous=FULL;
CREATE TABLE events(id INTEGER PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO events(value) VALUES('baseline');
SQL

time_txn_ms() {
	local value="$1"
	local start_ns end_ns
	start_ns=$(date +%s%N)
	sqlite3 "$DB" "PRAGMA synchronous=FULL; BEGIN IMMEDIATE; INSERT INTO events(value) VALUES('$value'); COMMIT;" >/dev/null
	end_ns=$(date +%s%N)
	echo $(( (end_ns - start_ns) / 1000000 ))
}

baseline_ms=$(time_txn_ms baseline_txn)

printf '50\n' > "$PARAMS/latency_ms"
delayed_ms=$(time_txn_ms delayed_txn)
printf '0\n' > "$PARAMS/latency_ms"

printf 'SQLite baseline transaction: %d ms\n' "$baseline_ms"
printf 'SQLite transaction with 50 ms I/O latency: %d ms\n' "$delayed_ms"

if (( delayed_ms <= baseline_ms + 40 )); then
	echo "FAIL: SQLite transaction did not show expected latency increase" >&2
	exit 1
fi
echo "PASS: SQLite transaction slowed under injected storage latency"

printf '100\n' > "$PARAMS/write_fail_pct"
set +e
failure_output=$(sqlite3 "$DB" "PRAGMA synchronous=FULL; BEGIN IMMEDIATE; INSERT INTO events(value) VALUES('must_fail'); COMMIT;" 2>&1)
failure_rc=$?
set -e
printf '0\n' > "$PARAMS/write_fail_pct"

if (( failure_rc == 0 )); then
	echo "FAIL: SQLite transaction succeeded with write_fail_pct=100" >&2
	exit 1
fi

printf 'SQLite observed injected storage failure: %s\n' "$(printf '%s\n' "$failure_output" | head -n 1)"
echo "PASS: SQLite surfaced the injected block-device write failure"
