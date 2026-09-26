# Fault Simulation Disk

[![CI](https://github.com/yyan115/faultsimdisk/actions/workflows/build.yml/badge.svg)](https://github.com/yyan115/faultsimdisk/actions/workflows/build.yml) [![Runtime Integration](https://github.com/yyan115/faultsimdisk/actions/workflows/runtime.yml/badge.svg)](https://github.com/yyan115/faultsimdisk/actions/workflows/runtime.yml)

**Make a Linux block device deliberately slow or unreliable, then observe how real filesystems and databases react.**

Fault Simulation Disk is a Linux kernel module that exposes `/dev/faultsim0` as a normal block device. Instead of damaging hardware or waiting for a real disk to fail, you can inject controlled storage faults at runtime and test the software above it.

## What can it simulate?

There are exactly three runtime fault controls:

| Control | Range | What it does |
| --- | ---: | --- |
| `latency_ms` | 0–5000 ms | Delays completion of every block I/O request |
| `read_fail_pct` | 0–100% | Completes the configured percentage of reads with an I/O error |
| `write_fail_pct` | 0–100% | Completes the configured percentage of writes with an I/O error |

The controls can be changed while the device is running, so a workload can start normally and then experience a slow or failing disk without restarting the application.

## What is being tested?

The applications are real. **The disk underneath them is the part being simulated.**

```text
SQLite / PostgreSQL          fio / raw I/O
        ↓                          ↓
       ext4                        │
        └──────────┬───────────────┘
                   ↓
          Linux block layer
                   ↓
            /dev/faultsim0
                   ↓
            FaultSimDisk
          ┌────────┼────────┐
          ↓        ↓        ↓
       latency   read I/O  write I/O
       delay     errors    errors
```

This lets the validation answer concrete questions:

- Can a normal filesystem format, mount, write, sync, and read back through the simulated disk?
- Does injected block latency actually propagate into raw I/O, `fio`, SQLite transactions, and durable PostgreSQL commits?
- Does a forced read failure reach userspace as a real I/O failure?
- Does a forced write failure propagate through ext4 into SQLite and PostgreSQL instead of being hidden?
- Does the kernel module correctly account for requests, bytes, failures, and delayed I/O?

## Live hosted demonstration

**The card below is not hand-written benchmark data.** GitHub Actions builds and loads the kernel module on a fresh hosted VM, runs the complete validation suite, parses the raw output, and regenerates this card automatically.

[![Live Fault Simulation Disk validation](https://raw.githubusercontent.com/yyan115/faultsimdisk/validation-results/latest.svg)](https://github.com/yyan115/faultsimdisk/tree/validation-results)

[Generated report](https://github.com/yyan115/faultsimdisk/tree/validation-results) · [Machine-readable JSON](https://raw.githubusercontent.com/yyan115/faultsimdisk/validation-results/latest.json) · [Raw validation output](https://raw.githubusercontent.com/yyan115/faultsimdisk/validation-results/raw/validation-output.txt) · [Reproducibility model](docs/reproducibility.md)

The hosted suite exercises all three fault controls. `fio` and the raw checks access `/dev/faultsim0` directly; SQLite and PostgreSQL run on ext4 backed by the device. PostgreSQL uses `fsync=on` and `synchronous_commit=on` so the test observes real durable-write behavior.

## Run it

Use a disposable Linux VM.

```bash
sudo apt install build-essential "linux-headers-$(uname -r)" kmod e2fsprogs fio sqlite3 python3 postgresql postgresql-client

make
./scripts/dev.sh load 256
./scripts/dev.sh validate
./scripts/dev.sh unload
```

To inject faults manually:

```bash
./scripts/dev.sh set latency_ms 100
./scripts/dev.sh set read_fail_pct 5
./scripts/dev.sh set write_fail_pct 10

./scripts/dev.sh config
./scripts/dev.sh stats
```

Configuration lives under `/sys/module/faultsimdisk/parameters/`. Runtime counters are exposed through `/sys/kernel/debug/faultsimdisk/stats`.

## Implementation

- Registers a functional Linux block device that can be formatted and mounted with ext4.
- Uses an in-memory backing store so experiments are disposable.
- Completes delayed I/O asynchronously through a dedicated workqueue rather than sleeping in `submit_bio`.
- Injects independent probabilistic read and write errors as `BLK_STS_IOERR`.
- Supports FLUSH, DISCARD, and WRITE_ZEROES semantics appropriate for the in-memory device.
- Tracks read/write requests, transferred bytes, failures, and delayed requests through atomic counters.
- Includes kernel API compatibility around the `blk_alloc_disk()` change after Linux 6.8.
- Includes DKMS packaging, hosted runtime validation, raw evidence, hashes, and GitHub artifact attestations.

## DKMS installation

For persistent installation across kernel updates:

```bash
sudo apt install dkms build-essential "linux-headers-$(uname -r)"
sudo ./scripts/install-dkms.sh
```

See [design notes](docs/design.md), [validation scenarios](docs/validation.md), [reproducibility and evidence](docs/reproducibility.md), and [contributing guidelines](CONTRIBUTING.md) for details.
