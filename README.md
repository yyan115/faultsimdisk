# Fault Simulation Disk

[![CI](https://github.com/yyan115/faultsimdisk/actions/workflows/build.yml/badge.svg)](https://github.com/yyan115/faultsimdisk/actions/workflows/build.yml) [![Runtime Integration](https://github.com/yyan115/faultsimdisk/actions/workflows/runtime.yml/badge.svg)](https://github.com/yyan115/faultsimdisk/actions/workflows/runtime.yml)

A Linux kernel module for testing how software handles slow or failing storage.

Fault Simulation Disk creates a RAM-backed block device at `/dev/faultsim0`. You can format it, mount it, and run applications on it, then add latency or make reads and writes fail while those applications are running. The tests use ext4, fio, SQLite and PostgreSQL to check how the faults reach user space.

## Fault controls

| Parameter | Range | Effect |
| --- | ---: | --- |
| `latency_ms` | 0 to 5000 ms | Adds a delay to each I/O handled by the driver. |
| `read_fail_pct` | 0 to 100% | Chance of returning an I/O error for each read. |
| `write_fail_pct` | 0 to 100% | Chance of returning an I/O error for each write. |

All three can be changed at runtime through `/sys/module/faultsimdisk/parameters/`. Request counts, transferred bytes, failures and delayed I/O are available in `/sys/kernel/debug/faultsimdisk/stats`.

## Test results

GitHub Actions builds the module and runs the integration tests on a hosted Ubuntu VM. The card below shows the latest successful run. The report links to its source commit, environment and raw output.

[![Fault Simulation Disk test results](https://raw.githubusercontent.com/yyan115/faultsimdisk/validation-results/latest.svg)](https://github.com/yyan115/faultsimdisk/tree/validation-results)

[Report](https://github.com/yyan115/faultsimdisk/tree/validation-results) · [JSON](https://raw.githubusercontent.com/yyan115/faultsimdisk/validation-results/latest.json) · [Raw output](https://raw.githubusercontent.com/yyan115/faultsimdisk/validation-results/raw/validation-output.txt) · [Evidence and verification](docs/reproducibility.md)

The suite checks filesystem operations, DISCARD and WRITE_ZEROES, latency, forced I/O errors and runtime counters. It also measures fio throughput and database transaction times with faults enabled. SQLite uses `synchronous=FULL`. PostgreSQL uses `fsync=on` and `synchronous_commit=on`.

The device loses its contents when the module is unloaded or the machine restarts. The database tests exercise synchronization and error handling, not persistence through a power loss.

## Build and run

Use a disposable Linux VM. The integration tests format `/dev/faultsim0` and overwrite its contents.

On Ubuntu:

```bash
sudo apt install build-essential "linux-headers-$(uname -r)" kmod e2fsprogs fio sqlite3 python3 postgresql postgresql-client util-linux

make
./scripts/dev.sh load 256
./scripts/dev.sh validate
./scripts/dev.sh unload
```

To try the controls yourself, load the device again:

```bash
./scripts/dev.sh load 256
./scripts/dev.sh set latency_ms 100
./scripts/dev.sh set read_fail_pct 5
./scripts/dev.sh set write_fail_pct 10

./scripts/dev.sh config
./scripts/dev.sh stats
```

Set a control to `0` to disable it. When finished, unmount any filesystem on the device and run `./scripts/dev.sh unload`.

## Implementation

The driver handles BIOs in [`faultsimdisk.c`](faultsimdisk.c). Reads and writes copy data to and from the backing memory under a spinlock. Delayed I/O runs on a workqueue, and failed requests complete with `BLK_STS_IOERR`. On unload, the driver drains pending work before releasing the backing memory.

DISCARD and WRITE_ZEROES clear the requested ranges. The device has no separate write cache to flush. A compatibility branch handles the `blk_alloc_disk()` API change between Linux 6.8 and 6.9.

The [design notes](docs/design.md) cover the I/O path and lifetime management. The [validation guide](docs/validation.md) describes each test.

## DKMS

DKMS can rebuild the module when the kernel is updated:

```bash
sudo apt install dkms build-essential "linux-headers-$(uname -r)" util-linux
sudo ./scripts/install-dkms.sh
```

To remove that version, run `sudo ./scripts/uninstall-dkms.sh` from the same checkout.

See [CHANGELOG.md](CHANGELOG.md) for release history. Licensed under [GPL-2.0](LICENSE).
