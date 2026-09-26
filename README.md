# Fault Simulation Disk

A Linux kernel block-device simulator for reproducible storage fault testing.

Fault Simulation Disk exposes `/dev/faultsim0` as a normal block device and can inject storage latency or read/write failures at runtime.

```text
application / filesystem
        ↓
Linux block layer
        ↓
/dev/faultsim0
        ↓
FaultSimDisk
   ├─ configurable latency
   ├─ configurable I/O failures
   ├─ runtime statistics
   └─ in-memory backing store
```

## Features

- Functional Linux block device that can be formatted and mounted with ext4
- Runtime-configurable latency from 0 to 5000 ms
- Independent read and write failure rates from 0 to 100%
- Deferred I/O completion through a dedicated workqueue
- Atomic request, byte, failure, and delayed-I/O counters through debugfs
- Automated raw-I/O, `fio`, filesystem, and SQLite validation scenarios

## Build and validate

Use a disposable Linux VM.

```bash
sudo apt install build-essential "linux-headers-$(uname -r)" kmod e2fsprogs fio sqlite3 python3

make
./scripts/dev.sh load
./scripts/dev.sh validate
./scripts/dev.sh unload
```

## Runtime controls

```bash
./scripts/dev.sh set latency_ms 100
./scripts/dev.sh set read_fail_pct 5
./scripts/dev.sh set write_fail_pct 10

./scripts/dev.sh config
./scripts/dev.sh stats
```

Configuration lives under `/sys/module/faultsimdisk/parameters/`; statistics are exposed through `/sys/kernel/debug/faultsimdisk/stats`.

## Validation snapshot

On Ubuntu 26.04 with Linux 7.0.0-34, a 4 KiB QD1 random-read test measured **518k IOPS baseline vs 47.5 IOPS with 20 ms injected latency**. A SQLite full-synchronous transaction increased from **6 ms to 262 ms** with 50 ms storage latency, and a 100% write-failure policy surfaced as a SQLite disk I/O error.

See [design notes](docs/design.md) and [validation scenarios](docs/validation.md) for details.
