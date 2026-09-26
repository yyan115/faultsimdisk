#!/usr/bin/env bash
set -euo pipefail

DEVICE=/dev/faultsim0
PARAMS=/sys/module/faultsimdisk/parameters
TMP_DIR=$(mktemp -d /tmp/faultsimdisk-fio.XXXXXX)

cleanup() {
	printf '0\n' > "$PARAMS/latency_ms" 2>/dev/null || true
	printf '0\n' > "$PARAMS/read_fail_pct" 2>/dev/null || true
	printf '0\n' > "$PARAMS/write_fail_pct" 2>/dev/null || true
	rm -rf "$TMP_DIR"
}
trap cleanup EXIT

if (( EUID != 0 )); then
	echo "Run through: ./scripts/dev.sh fio-test" >&2
	exit 1
fi

command -v fio >/dev/null || { echo "Missing fio. Install: sudo apt install fio" >&2; exit 1; }
command -v python3 >/dev/null || { echo "Missing python3." >&2; exit 1; }
test -b "$DEVICE" || { echo "$DEVICE is not a block device." >&2; exit 1; }

if findmnt -rn -S "$DEVICE" >/dev/null; then
	echo "$DEVICE must not be mounted during the raw fio benchmark." >&2
	exit 1
fi

reset_faults() {
	printf '0\n' > "$PARAMS/latency_ms"
	printf '0\n' > "$PARAMS/read_fail_pct"
	printf '0\n' > "$PARAMS/write_fail_pct"
}
reset_faults

run_read_benchmark() {
	local output="$1"
	fio 		--name=faultsim-read 		--filename="$DEVICE" 		--rw=randread 		--bs=4k 		--ioengine=psync 		--direct=1 		--iodepth=1 		--numjobs=1 		--time_based=1 		--runtime=2 		--group_reporting=1 		--output-format=json 		--output="$output"
}

baseline_json="$TMP_DIR/baseline.json"
delayed_json="$TMP_DIR/delayed.json"

run_read_benchmark "$baseline_json"

printf '20\n' > "$PARAMS/latency_ms"
run_read_benchmark "$delayed_json"
printf '0\n' > "$PARAMS/latency_ms"

python3 - "$baseline_json" "$delayed_json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    baseline = json.load(f)
with open(sys.argv[2], encoding="utf-8") as f:
    delayed = json.load(f)

baseline_iops = float(baseline["jobs"][0]["read"]["iops"])
delayed_iops = float(delayed["jobs"][0]["read"]["iops"])

print(f"fio baseline randread IOPS: {baseline_iops:.1f}")
print(f"fio with 20 ms injected latency: {delayed_iops:.1f} IOPS")

if baseline_iops <= delayed_iops:
    raise SystemExit("FAIL: injected latency did not reduce IOPS")
if delayed_iops >= 100:
    raise SystemExit("FAIL: 20 ms latency should constrain single-depth IOPS below 100")

print("PASS: fio measured the expected performance impact from injected latency")
PY
