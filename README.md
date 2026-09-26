# Fault Simulation Disk

[![CI](https://github.com/yyan115/faultsimdisk/actions/workflows/build.yml/badge.svg)](https://github.com/yyan115/faultsimdisk/actions/workflows/build.yml) [![Runtime Integration](https://github.com/yyan115/faultsimdisk/actions/workflows/runtime.yml/badge.svg)](https://github.com/yyan115/faultsimdisk/actions/workflows/runtime.yml)

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
- Automated raw-I/O, `fio`, filesystem, SQLite, and PostgreSQL validation scenarios

## Build and validate

Use a disposable Linux VM.

```bash
sudo apt install build-essential "linux-headers-$(uname -r)" kmod e2fsprogs fio sqlite3 python3 postgresql postgresql-client

make
./scripts/dev.sh load 256
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

## Validation

The primary validation runs on a fresh GitHub-hosted Ubuntu VM and checks behavior rather than requiring one machine-specific performance number. The workflow builds and loads the kernel module, exercises ext4, latency and error injection, runtime statistics, `fio`, SQLite, and a disposable PostgreSQL cluster with `fsync` and synchronous commit enabled. It uploads the runner environment and full test output as CI artifacts tied to the tested commit.

Local Linux 7.0 results are retained in the detailed validation notes as compatibility evidence, not as portable performance claims.

See [design notes](docs/design.md), [validation scenarios](docs/validation.md), [reproducibility and evidence](docs/reproducibility.md), and [contributing guidelines](CONTRIBUTING.md) for details.

## Installation

For normal development, build against the running kernel with `make`. For persistent installation across kernel updates, DKMS support is included:

```bash
sudo apt install dkms
sudo ./scripts/install-dkms.sh
```

Tagged `v*` releases automatically publish a source archive and checksum through GitHub Releases.
