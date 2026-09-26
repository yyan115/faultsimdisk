#!/usr/bin/env bash
set -euo pipefail

DEVICE=/dev/faultsim0
PARAMS=/sys/module/faultsimdisk/parameters
DEBUGFS=/sys/kernel/debug
STATS=$DEBUGFS/faultsimdisk/stats
mounted_here=0

cleanup() {
	printf '0\n' > "$PARAMS/latency_ms" 2>/dev/null || true
	printf '0\n' > "$PARAMS/read_fail_pct" 2>/dev/null || true
	printf '0\n' > "$PARAMS/write_fail_pct" 2>/dev/null || true
	if (( mounted_here )); then
		umount "$DEBUGFS" 2>/dev/null || true
	fi
}
trap cleanup EXIT

if (( EUID != 0 )); then
	echo "Run through: ./scripts/dev.sh stats-test" >&2
	exit 1
fi

test -b "$DEVICE" || { echo "$DEVICE is not a block device." >&2; exit 1; }
if findmnt -rn -S "$DEVICE" >/dev/null; then
	echo "$DEVICE must not be mounted during the raw stats test." >&2
	exit 1
fi

if ! mountpoint -q "$DEBUGFS"; then
	mount -t debugfs debugfs "$DEBUGFS"
	mounted_here=1
fi

test -r "$STATS" || { echo "Missing debugfs stats file: $STATS" >&2; exit 1; }

stat_value() {
	awk -v key="$1" '$1 == key { print $2; exit }' "$STATS"
}

printf '0\n' > "$PARAMS/latency_ms"
printf '0\n' > "$PARAMS/read_fail_pct"
printf '0\n' > "$PARAMS/write_fail_pct"

before_reads=$(stat_value read_requests)
before_read_bytes=$(stat_value read_bytes)
dd if="$DEVICE" of=/dev/null bs=4096 count=1 iflag=direct status=none
after_reads=$(stat_value read_requests)
after_read_bytes=$(stat_value read_bytes)

(( after_reads > before_reads ))
(( after_read_bytes >= before_read_bytes + 4096 ))
echo "PASS: read request and byte counters increased"

before_writes=$(stat_value write_requests)
before_write_bytes=$(stat_value write_bytes)
dd if=/dev/zero of="$DEVICE" bs=4096 count=1 oflag=direct,dsync status=none
after_writes=$(stat_value write_requests)
after_write_bytes=$(stat_value write_bytes)

(( after_writes > before_writes ))
(( after_write_bytes >= before_write_bytes + 4096 ))
echo "PASS: write request and byte counters increased"

before_failed=$(stat_value failed_writes)
printf '100\n' > "$PARAMS/write_fail_pct"
if dd if=/dev/zero of="$DEVICE" bs=4096 count=1 oflag=direct status=none 2>/dev/null; then
	echo "FAIL: write unexpectedly succeeded with write_fail_pct=100" >&2
	exit 1
fi
after_failed=$(stat_value failed_writes)
(( after_failed > before_failed ))
echo "PASS: failed write counter increased"

printf '0\n' > "$PARAMS/write_fail_pct"
before_delayed=$(stat_value delayed_requests)
printf '50\n' > "$PARAMS/latency_ms"
dd if="$DEVICE" of=/dev/null bs=4096 count=1 iflag=direct status=none
after_delayed=$(stat_value delayed_requests)
(( after_delayed > before_delayed ))
echo "PASS: delayed request counter increased"

printf '0\n' > "$PARAMS/latency_ms"
echo "PASS: Stage 3 statistics checks completed"
