# Validation

All destructive tests target only `/dev/faultsim0`. Run them inside a disposable VM with the module loaded.

## Full validation

```bash
sudo apt install fio sqlite3 python3 e2fsprogs postgresql postgresql-client
./scripts/dev.sh load 256
./scripts/dev.sh validate
```

The suite performs:

1. **Filesystem smoke test**: creates ext4 on Fault Simulation Disk, mounts it, writes and reads a file.
2. **Fault injection test**: verifies configured 100 ms latency and deterministic 100% read/write failures.
3. **Statistics test**: confirms request, byte, failure, and delayed-I/O counters increase.
4. **fio benchmark**: compares 4 KiB single-depth random reads at baseline and with 20 ms injected latency.
5. **SQLite scenario**: runs full-synchronous transactions on ext4 backed by Fault Simulation Disk, measures injected latency, then confirms a 100% write-failure policy surfaces as an application error.
6. **PostgreSQL scenario**: initializes a disposable PostgreSQL cluster directly on Fault Simulation Disk with `fsync=on` and `synchronous_commit=on`, measures durable commit latency, then injects block write failure and records the server/client-visible error.

The suite resets fault settings after each scenario.

## Application-level failure propagation

SQLite and PostgreSQL both depend on the filesystem and block device beneath their database files. PostgreSQL is tested with durability settings enabled so commits wait for WAL flushes rather than using non-durable shortcuts.

SQLite depends on the filesystem and block device beneath its database file. When Fault Simulation Disk completes writes with I/O errors, the failure propagates through the Linux storage stack to SQLite, allowing the application-visible behavior to be tested without failing physical storage.


## Recorded validation run

Environment:

- Ubuntu 26.04 LTS
- Linux 7.0.0-34-generic
- fio 3.41
- SQLite 3.46.1
- 64 MiB Fault Simulation Disk

Observed results:

- ext4 format, mount, synchronized write, readback, and unmount completed successfully;
- configured 100 ms raw-read latency measured 113 ms end to end;
- 100% read and write failure policies rejected their corresponding raw I/O operations;
- 4 KiB QD1 random-read performance measured 518,012.5 IOPS at baseline and 47.5 IOPS with 20 ms injected latency;
- a full-synchronous SQLite transaction measured 6 ms at baseline and 262 ms with 50 ms injected storage latency;
- a 100% write-failure policy propagated through ext4 to SQLite as `disk I/O error (10)`;
- the final statistics snapshot recorded 1,036,953 read requests, 225 write requests, 1 failed read, 3 failed writes, and 109 delayed requests.

These values are a validation snapshot from one VM run, not hardware performance guarantees.
