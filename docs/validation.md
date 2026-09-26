# Validation

All destructive tests target only `/dev/faultsim0`. Run them inside a disposable VM with the module loaded.

## Full validation

```bash
sudo apt install fio sqlite3 python3 e2fsprogs
./scripts/dev.sh validate
```

The suite performs:

1. **Filesystem smoke test**: creates ext4 on Fault Simulation Disk, mounts it, writes and reads a file.
2. **Fault injection test**: verifies configured 100 ms latency and deterministic 100% read/write failures.
3. **Statistics test**: confirms request, byte, failure, and delayed-I/O counters increase.
4. **fio benchmark**: compares 4 KiB single-depth random reads at baseline and with 20 ms injected latency.
5. **SQLite scenario**: runs full-synchronous transactions on ext4 backed by Fault Simulation Disk, measures injected latency, then confirms a 100% write-failure policy surfaces as an application error.

The suite resets fault settings after each scenario.

## Application-level failure propagation

SQLite depends on the filesystem and block device beneath its database file. When Fault Simulation Disk completes writes with I/O errors, the failure propagates through the Linux storage stack to SQLite, allowing the application-visible behavior to be tested without failing physical storage.
