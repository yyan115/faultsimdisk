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

require_loaded() {
	test -d /sys/module/faultsimdisk || {
		echo "faultsimdisk is not loaded." >&2
		exit 1
	}
}

show_config() {
	for name in latency_ms read_fail_pct write_fail_pct; do
		printf '%-16s %s\n' "$name" "$(cat "/sys/module/faultsimdisk/parameters/$name")"
	done
}

ensure_debugfs() {
	if ! mountpoint -q /sys/kernel/debug; then
		sudo mount -t debugfs debugfs /sys/kernel/debug
	fi
}

show_stats() {
	require_loaded
	ensure_debugfs
	sudo cat /sys/kernel/debug/faultsimdisk/stats
}

case "${1:-}" in
	load)
		require_vm
		test -f faultsimdisk.ko || { echo "Build first with: make" >&2; exit 1; }
		test ! -d /sys/module/faultsimdisk || { echo "faultsimdisk is already loaded." >&2; exit 1; }
		if test -n "${2:-}"; then
			sudo insmod ./faultsimdisk.ko size_mb="$2"
		else
			sudo insmod ./faultsimdisk.ko
		fi
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
			show_config
		else
			echo "faultsimdisk: not loaded"
		fi
		;;
	config)
		require_loaded
		show_config
		;;
	set)
		require_vm
		require_loaded
		name="${2:-}"
		value="${3:-}"
		case "$name" in
			latency_ms|read_fail_pct|write_fail_pct) ;;
			*)
				echo "Unknown setting: $name" >&2
				exit 2
				;;
		esac
		test -n "$value" || { echo "Usage: $0 set <setting> <value>" >&2; exit 2; }
		printf '%s\n' "$value" | sudo tee "/sys/module/faultsimdisk/parameters/$name" >/dev/null
		printf '%s=%s\n' "$name" "$(cat "/sys/module/faultsimdisk/parameters/$name")"
		;;
	stats)
		show_stats
		;;
	logs)
		sudo dmesg --color=never | grep -E 'faultsimdisk|faultsim0' | tail -n 30
		;;
	smoke)
		require_vm
		sudo "$ROOT/scripts/smoke-test.sh"
		;;
	fault-test)
		require_vm
		sudo "$ROOT/scripts/fault-test.sh"
		;;
	stats-test)
		require_vm
		sudo "$ROOT/scripts/stats-test.sh"
		;;
	fio-test)
		require_vm
		sudo "$ROOT/scripts/fio-test.sh"
		;;
	sqlite-test)
		require_vm
		sudo "$ROOT/scripts/sqlite-test.sh"
		;;
	postgres-test)
		require_vm
		sudo "$ROOT/scripts/postgres-test.sh"
		;;
	validate)
		require_vm
		require_loaded
		"$ROOT/scripts/final-validate.sh"
		;;
	*)
		echo "Usage: $0 {load [size_mb]|unload|status|config|set|stats|logs|smoke|fault-test|stats-test|fio-test|sqlite-test|postgres-test|validate}" >&2
		exit 2
		;;
esac
