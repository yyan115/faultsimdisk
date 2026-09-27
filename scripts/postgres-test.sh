#!/usr/bin/env bash
set -euo pipefail

DEVICE=/dev/faultsim0
PARAMS=/sys/module/faultsimdisk/parameters
MOUNT_DIR=$(mktemp -d /tmp/faultsimdisk-postgres.XXXXXX)
SOCKET_DIR=$(mktemp -d /tmp/faultsimdisk-pg-socket.XXXXXX)
LOG_FILE=$(mktemp /tmp/faultsimdisk-postgres.XXXXXX.log)
PGDATA="$MOUNT_DIR/data"
PORT=55432
mounted=0
server_started=0

reset_faults() {
	printf '0\n' > "$PARAMS/latency_ms" 2>/dev/null || true
	printf '0\n' > "$PARAMS/read_fail_pct" 2>/dev/null || true
	printf '0\n' > "$PARAMS/write_fail_pct" 2>/dev/null || true
}

cleanup() {
	reset_faults

	if (( server_started )); then
		runuser -u postgres -- "$PG_CTL" -D "$PGDATA" -m immediate stop >/dev/null 2>&1 || true
	fi

	if (( mounted )); then
		sync || true
		umount "$MOUNT_DIR" 2>/dev/null || umount -l "$MOUNT_DIR" 2>/dev/null || true
	fi

	rm -rf "$SOCKET_DIR"
	rm -f "$LOG_FILE"
	rmdir "$MOUNT_DIR" 2>/dev/null || true
}
trap cleanup EXIT

if (( EUID != 0 )); then
	echo "Run through: ./scripts/dev.sh postgres-test" >&2
	exit 1
fi

for cmd in pg_config runuser timeout; do
	command -v "$cmd" >/dev/null || {
		echo "Missing dependency: $cmd" >&2
		echo "Install with: sudo apt install postgresql postgresql-client" >&2
		exit 1
	}
done

test -b "$DEVICE" || { echo "$DEVICE is not a block device." >&2; exit 1; }
test -d /sys/module/faultsimdisk || { echo "faultsimdisk is not loaded." >&2; exit 1; }
test -d /sys/block/faultsim0 || { echo "Refusing unexpected device." >&2; exit 1; }
test "$(lsblk -dn -o KNAME "$DEVICE" 2>/dev/null || true)" = "faultsim0" || {
	echo "Refusing unexpected device node: $DEVICE" >&2
	exit 1
}

if findmnt -rn -S "$DEVICE" >/dev/null; then
	echo "$DEVICE is already mounted." >&2
	exit 1
fi

capacity_bytes=$(blockdev --getsize64 "$DEVICE")
if (( capacity_bytes < 134217728 )); then
	echo "PostgreSQL validation requires at least 128 MiB." >&2
	echo "Reload with: ./scripts/dev.sh unload && ./scripts/dev.sh load 256" >&2
	exit 1
fi

BINDIR=$(pg_config --bindir)
INITDB="$BINDIR/initdb"
PG_CTL="$BINDIR/pg_ctl"
PSQL="$BINDIR/psql"

for binary in "$INITDB" "$PG_CTL" "$PSQL"; do
	test -x "$binary" || { echo "Missing PostgreSQL binary: $binary" >&2; exit 1; }
done

reset_faults
mkfs.ext4 -q -F "$DEVICE"
mount "$DEVICE" "$MOUNT_DIR"
mounted=1

install -d -o postgres -g postgres "$PGDATA"
chown postgres:postgres "$SOCKET_DIR" "$LOG_FILE"

runuser -u postgres -- "$INITDB" -D "$PGDATA" --auth=trust --no-locale --encoding=UTF8 >/dev/null

runuser -u postgres -- "$PG_CTL" \
	-D "$PGDATA" \
	-l "$LOG_FILE" \
	-o "-k $SOCKET_DIR -p $PORT -c listen_addresses='' -c fsync=on -c synchronous_commit=on -c full_page_writes=on" \
	-w start >/dev/null
server_started=1

psql_cmd=("$PSQL" -h "$SOCKET_DIR" -p "$PORT" -U postgres -d postgres -v ON_ERROR_STOP=1)

"${psql_cmd[@]}" -c "CREATE TABLE events(id bigserial PRIMARY KEY, value text NOT NULL);" >/dev/null

time_txn_ms() {
	local value="$1"
	local start_ns end_ns

	start_ns=$(date +%s%N)
	"${psql_cmd[@]}" -c "SET synchronous_commit=on; INSERT INTO events(value) VALUES('$value');" >/dev/null
	end_ns=$(date +%s%N)

	echo $(( (end_ns - start_ns) / 1000000 ))
}

baseline_ms=$(time_txn_ms baseline)

printf '50\n' > "$PARAMS/latency_ms"
delayed_ms=$(time_txn_ms delayed)
printf '0\n' > "$PARAMS/latency_ms"

printf 'PostgreSQL baseline synchronous commit: %d ms\n' "$baseline_ms"
printf 'PostgreSQL transaction with 50 ms I/O latency: %d ms\n' "$delayed_ms"

if (( delayed_ms <= baseline_ms + 40 )); then
	echo "FAIL: PostgreSQL transaction did not show expected latency increase" >&2
	exit 1
fi
echo "PASS: PostgreSQL synchronous commit slowed under injected storage latency"

printf '100\n' > "$PARAMS/write_fail_pct"
set +e
failure_output=$(timeout 10s "${psql_cmd[@]}" -c "SET synchronous_commit=on; INSERT INTO events(value) VALUES('must_fail');" 2>&1)
failure_rc=$?
set -e
printf '0\n' > "$PARAMS/write_fail_pct"

if (( failure_rc == 0 )); then
	echo "FAIL: PostgreSQL transaction succeeded with write_fail_pct=100" >&2
	exit 1
fi

failure_line=$(printf '%s\n' "$failure_output" | grep -E -m1 'ERROR|FATAL|PANIC|server closed|connection' || true)
if test -z "$failure_line"; then
	failure_line=$(printf '%s\n' "$failure_output" | head -n 1)
fi
printf 'PostgreSQL observed injected storage failure: %s\n' "$failure_line"
echo "PASS: PostgreSQL surfaced the injected block-device write failure"
