#!/usr/bin/env bash
set -euo pipefail

DEVICE=/dev/faultsim0
PARAMS=/sys/module/faultsimdisk/parameters
SYSFS=/sys/block/faultsim0
BLOCK_SIZE=4096

reset_faults() {
	printf '0\n' > "$PARAMS/latency_ms" 2>/dev/null || true
	printf '0\n' > "$PARAMS/read_fail_pct" 2>/dev/null || true
	printf '0\n' > "$PARAMS/write_fail_pct" 2>/dev/null || true
}
trap reset_faults EXIT

if (( EUID != 0 )); then
	echo "Run through: ./scripts/dev.sh block-ops-test" >&2
	exit 1
fi

for cmd in blkdiscard blockdev lsblk python3; do
	command -v "$cmd" >/dev/null || { echo "Missing dependency: $cmd" >&2; exit 1; }
done

test -b "$DEVICE" || { echo "$DEVICE is not a block device." >&2; exit 1; }
test -d /sys/module/faultsimdisk || { echo "faultsimdisk is not loaded." >&2; exit 1; }
test -d "$SYSFS" || { echo "Refusing unexpected device." >&2; exit 1; }
test "$(lsblk -dn -o KNAME "$DEVICE" 2>/dev/null || true)" = "faultsim0" || {
	echo "Refusing unexpected device node: $DEVICE" >&2
	exit 1
}

if findmnt -rn -S "$DEVICE" >/dev/null; then
	echo "$DEVICE must not be mounted during the block operation test." >&2
	exit 1
fi

reset_faults

discard_max=$(cat "$SYSFS/queue/discard_max_bytes")
write_zeroes_max=$(cat "$SYSFS/queue/write_zeroes_max_bytes")
if (( discard_max == 0 )); then
	echo "FAIL: block queue does not advertise discard support" >&2
	exit 1
fi
if (( write_zeroes_max == 0 )); then
	echo "FAIL: block queue does not advertise write-zeroes support" >&2
	exit 1
fi
echo "PASS: block queue advertises discard and write-zeroes support"

capacity=$(blockdev --getsize64 "$DEVICE")
base_offset=$(( (capacity / 2 / BLOCK_SIZE) * BLOCK_SIZE ))
discard_offset=$base_offset
zeroes_offset=$(( base_offset + BLOCK_SIZE ))
if (( zeroes_offset + BLOCK_SIZE > capacity )); then
	echo "FAIL: device is too small for block operation validation" >&2
	exit 1
fi

write_pattern() {
	local offset="$1"
	local seek_blocks=$(( offset / BLOCK_SIZE ))
	dd if=/dev/urandom of="$DEVICE" bs="$BLOCK_SIZE" count=1 seek="$seek_blocks" \
		oflag=direct,dsync status=none
}

range_is_zero() {
	local offset="$1"
	local skip_blocks=$(( offset / BLOCK_SIZE ))
	dd if="$DEVICE" bs="$BLOCK_SIZE" count=1 skip="$skip_blocks" \
		iflag=direct status=none |
		python3 -c 'import sys; data=sys.stdin.buffer.read(); raise SystemExit(0 if len(data) == 4096 and not any(data) else 1)'
}

write_pattern "$discard_offset"
blkdiscard -f -q --offset "$discard_offset" --length "$BLOCK_SIZE" "$DEVICE"
range_is_zero "$discard_offset" || {
	echo "FAIL: discarded range did not read back as zero" >&2
	exit 1
}
echo "PASS: discard zeroed the requested range"

write_pattern "$zeroes_offset"
blkdiscard -f -q --zeroout --offset "$zeroes_offset" --length "$BLOCK_SIZE" "$DEVICE"
range_is_zero "$zeroes_offset" || {
	echo "FAIL: write-zeroes range did not read back as zero" >&2
	exit 1
}
echo "PASS: write-zeroes zeroed the requested range"
