#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

require_vm() {
	if systemd-detect-virt --container --quiet; then
		echo "Refusing to load a kernel module inside a container." >&2
		exit 1
	fi
	if ! systemd-detect-virt --vm --quiet; then
		echo "Refusing to load development kernel code outside a VM." >&2
		exit 1
	fi
}

case "${1:-}" in
	load)
		require_vm
		test -f faultsimdisk.ko || { echo "Build first with: make" >&2; exit 1; }
		test ! -d /sys/module/faultsimdisk || { echo "faultsimdisk is already loaded." >&2; exit 1; }
		sudo insmod ./faultsimdisk.ko
		for _ in $(seq 1 20); do
			test -b /dev/faultsim0 && break
			sleep 0.1
		done
		test -b /dev/faultsim0 || { echo "/dev/faultsim0 was not created." >&2; exit 1; }
		lsblk /dev/faultsim0
		;;
	unload)
		require_vm
		sudo rmmod faultsimdisk
		;;
	status)
		if test -d /sys/module/faultsimdisk; then
			echo "faultsimdisk: loaded"
			lsblk /dev/faultsim0
		else
			echo "faultsimdisk: not loaded"
		fi
		;;
	logs)
		sudo dmesg --color=never | grep -E 'faultsimdisk|faultsim0' | tail -n 30
		;;
	smoke)
		require_vm
		sudo "$ROOT/scripts/smoke-test.sh"
		;;
	*)
		echo "Usage: $0 {load|unload|status|logs|smoke}" >&2
		exit 2
		;;
esac
