# Validation

All destructive tests target only `/dev/faultsim0`. Run local validation inside a disposable VM with the module loaded.

## Hosted validation

The primary validation runs in GitHub Actions on a fresh hosted Ubuntu VM. The latest generated report is published on the repository's `validation-results` branch and is linked directly from the README.

Each hosted run records the exact commit, runner image, kernel, architecture, compiler, `fio`, SQLite, and PostgreSQL versions alongside the raw validation output and hashes.

## Full local validation

```bash
sudo apt install fio sqlite3 python3 e2fsprogs postgresql postgresql-client util-linux
./scripts/dev.sh load 256
./scripts/dev.sh validate
```

The suite performs:

1. **Filesystem smoke test**: creates ext4 on Fault Simulation Disk, mounts it, writes and reads a file.
2. **Block-operation test**: verifies Linux sees non-zero DISCARD and WRITE_ZEROES limits, executes both operations, and confirms the affected ranges read back as zero.
3. **Fault injection test**: verifies configured 100 ms latency and deterministic 100% read/write failures, capturing the userspace I/O errors.
4. **Statistics test**: confirms request, byte, failure, and delayed-I/O counters increase.
5. **fio benchmark**: compares 4 KiB single-depth random reads at baseline and with 20 ms injected latency.
6. **SQLite scenario**: runs full-synchronous transactions on ext4 backed by Fault Simulation Disk, measures injected latency, then confirms a 100% write-failure policy surfaces as an application error.
7. **PostgreSQL scenario**: initializes a disposable PostgreSQL cluster directly on Fault Simulation Disk with `fsync=on` and `synchronous_commit=on`, measures synchronous commit latency, then injects block write failure and records the server/client-visible error.

The suite resets fault settings after each scenario.

## Application-level failure propagation

SQLite and PostgreSQL both depend on the filesystem and block device beneath their database files. When Fault Simulation Disk completes writes with I/O errors, those failures propagate through the Linux storage stack to the database, allowing application-visible behavior to be tested without failing physical storage.

PostgreSQL is tested with its durability settings enabled so commits wait for WAL flushes rather than using asynchronous shortcuts. The RAM-backed simulator verifies that synchronization path and its error propagation, not persistence across host power loss.

## Recorded local compatibility run

An earlier local compatibility run used:

- Ubuntu 26.04 LTS
- Linux 7.0.0-34-generic
- fio 3.41
- SQLite 3.46.1
- 64 MiB Fault Simulation Disk

That run verified ext4 operation, raw latency and deterministic failures, statistics accounting, `fio` response to injected latency, and SQLite failure propagation. It predates the PostgreSQL scenario and is retained only as additional Linux 7.0 compatibility evidence.

Absolute measurements from local or hosted runs are not hardware performance guarantees.
