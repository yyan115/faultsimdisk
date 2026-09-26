#!/usr/bin/env bash
set -euo pipefail

DEVICE=/dev/faultsim0
MOUNT_DIR=$(mktemp -d /tmp/faultsimdisk.XXXXXX)

cleanup() {
	if mountpoint -q "$MOUNT_DIR"; then
		umount "$MOUNT_DIR"
	fi
	rmdir "$MOUNT_DIR" 2>/dev/null || true
}
trap cleanup EXIT

if (( EUID != 0 )); then
	echo "Run through: ./scripts/dev.sh smoke" >&2
	exit 1
fi

test -b "$DEVICE" || { echo "$DEVICE is not a block device." >&2; exit 1; }
test -d /sys/block/faultsim0 || { echo "Refusing unexpected device." >&2; exit 1; }

mkfs.ext4 -q -F "$DEVICE"
mount "$DEVICE" "$MOUNT_DIR"

printf 'Fault Simulation Disk smoke test\n' > "$MOUNT_DIR/probe.txt"
sync

actual=$(cat "$MOUNT_DIR/probe.txt")
test "$actual" = "Fault Simulation Disk smoke test"

echo "PASS: formatted, mounted, wrote, synced, and read back through $DEVICE"
