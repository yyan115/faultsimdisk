# Design

Fault Simulation Disk is a Linux block-device simulator for controlled storage failure experiments.

## I/O path

```text
userspace application
        ↓
filesystem / raw block I/O
        ↓
Linux block layer
        ↓
fsd_submit_bio()
        ↓
fault policy snapshot
        ↓
immediate completion OR delayed workqueue
        ↓
read/write against backing memory OR injected I/O error
        ↓
bio completion
```

The driver registers `/dev/faultsim0` and stores its sectors in zero-initialized kernel virtual memory.

### Latency injection

`submit_bio` may run in contexts where sleeping is unsafe, so configured latency is not implemented with a blocking sleep. Requests that need delay are moved to a dedicated delayed-work queue and completed later.

Delayed requests are explicitly counted while timer-pending or queued. Module unload removes the disk, waits until every delayed I/O callback has completed, then flushes and destroys the workqueue before freeing the backing store. This avoids destroying a workqueue while a `delayed_work` item still exists only on its timer.

### Failure injection

Read and write failure percentages are independently configurable. Each incoming read/write request samples the current percentage and either follows the normal data path or completes with `BLK_STS_IOERR`.

Configuration is exposed through writable module parameters:

```text
/sys/module/faultsimdisk/parameters/latency_ms
/sys/module/faultsimdisk/parameters/read_fail_pct
/sys/module/faultsimdisk/parameters/write_fail_pct
```

The parameters are validated in-kernel: latency is limited to 0-5000 ms and percentages to 0-100.

### Observability

The driver maintains atomic counters for submitted reads and writes, successful bytes transferred, failed read/write requests, and delayed requests. A read-only debugfs view exposes these counters at:

```text
/sys/kernel/debug/faultsimdisk/stats
```

Configuration remains in module parameters under sysfs, while diagnostic statistics live in debugfs.

### Backing store

A spinlock protects concurrent access to the in-memory backing store. Read and write BIO segments are copied while the relevant backing range is locked. Discard and write-zeroes operations clear the requested range in page-sized chunks so a large request does not keep interrupts disabled for the full range. The queue explicitly advertises both capabilities to the block layer; Linux 6.8 uses the legacy queue-limit setters, while Linux 6.9+ supplies them through the initial `queue_limits`. Flush completes immediately because there is no volatile hardware cache.

## Compatibility

A small compatibility branch handles the `blk_alloc_disk()` API change introduced after Linux 6.8 so CI can compile against Ubuntu 24.04 headers while runtime validation also exercises newer kernels.

## Validation

The repository validates the driver at multiple layers:

- raw block I/O verifies deterministic latency and read/write failure injection;
- block-operation checks verify DISCARD and WRITE_ZEROES are advertised and zero the requested ranges;
- debugfs checks verify request, byte, failure, and delayed-I/O accounting;
- `fio` compares single-depth random-read throughput with and without injected latency;
- SQLite runs on ext4 backed by `/dev/faultsim0`, validating transaction slowdown and application-visible I/O failure;
- PostgreSQL runs a disposable cluster with `fsync=on` and `synchronous_commit=on`, validating durable-commit latency and WAL write-failure propagation;
- GitHub-hosted runtime integration rebuilds and loads the module on a fresh runner and publishes the exact environment, raw output, structured results, hashes, and attested evidence.

Absolute performance numbers are environment-specific. The validation focuses on reproducible fault behavior and relative response to configured injection.
