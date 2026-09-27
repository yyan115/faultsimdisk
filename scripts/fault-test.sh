#!/usr/bin/env bash
set -euo pipefail

DEVICE=/dev/faultsim0
PARAMS=/sys/module/faultsimdisk/parameters

reset_faults() {
	printf '0\n' > "$PARAMS/latency_ms"
	printf '0\n' > "$PARAMS/read_fail_pct"
	printf '0\n' > "$PARAMS/write_fail_pct"
}
trap reset_faults EXIT

if (( EUID != 0 )); then
	echo "Run through: ./scripts/dev.sh fault-test" >&2
	exit 1
fi

test -b "$DEVICE" || { echo "$DEVICE is not a block device." >&2; exit 1; }
test -d /sys/module/faultsimdisk || { echo "faultsimdisk is not loaded." >&2; exit 1; }
test -d /sys/block/faultsim0 || { echo "Refusing unexpected device." >&2; exit 1; }
test "$(lsblk -dn -o KNAME "$DEVICE" 2>/dev/null || true)" = "faultsim0" || {
	echo "Refusing unexpected device node: $DEVICE" >&2
	exit 1
}

if findmnt -rn -S "$DEVICE" >/dev/null; then
	echo "$DEVICE must not be mounted during the raw I/O fault test." >&2
	exit 1
fi

reset_faults

printf '100\n' > "$PARAMS/latency_ms"
start_ns=$(date +%s%N)
dd if="$DEVICE" of=/dev/null bs=4096 count=1 iflag=direct status=none
end_ns=$(date +%s%N)
elapsed_ms=$(( (end_ns - start_ns) / 1000000 ))

if (( elapsed_ms < 80 )); then
	echo "FAIL: expected at least ~100 ms latency, measured ${elapsed_ms} ms" >&2
	exit 1
fi
printf 'PASS: 100 ms configured latency produced %d ms raw-read latency\n' "$elapsed_ms"

printf '0\n' > "$PARAMS/latency_ms"
printf '100\n' > "$PARAMS/write_fail_pct"
set +e
write_failure_output=$(dd if=/dev/zero of="$DEVICE" bs=4096 count=1 oflag=direct status=none 2>&1)
write_failure_rc=$?
set -e
if (( write_failure_rc == 0 )); then
	echo "FAIL: write succeeded with write_fail_pct=100" >&2
	exit 1
fi
write_failure_line=$(printf '%s\n' "$write_failure_output" | grep -E -m1 'error|Error|failed' || true)
test -n "$write_failure_line" || write_failure_line="write failed with exit code $write_failure_rc"
printf 'Raw write observed injected failure: %s\n' "$write_failure_line"
echo "PASS: write_fail_pct=100 rejected a raw write"

printf '0\n' > "$PARAMS/write_fail_pct"
printf '100\n' > "$PARAMS/read_fail_pct"
set +e
read_failure_output=$(dd if="$DEVICE" of=/dev/null bs=4096 count=1 iflag=direct status=none 2>&1)
read_failure_rc=$?
set -e
if (( read_failure_rc == 0 )); then
	echo "FAIL: read succeeded with read_fail_pct=100" >&2
	exit 1
fi
read_failure_line=$(printf '%s\n' "$read_failure_output" | grep -E -m1 'error|Error|failed' || true)
test -n "$read_failure_line" || read_failure_line="read failed with exit code $read_failure_rc"
printf 'Raw read observed injected failure: %s\n' "$read_failure_line"
echo "PASS: read_fail_pct=100 rejected a raw read"

reset_faults
echo "PASS: latency and failure injection checks completed"
