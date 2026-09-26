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

`submit_bio` may run in contexts where sleeping is unsafe, so configured latency is not implemented with a blocking sleep. Requests that need delay are moved to a dedicated delayed-work queue and completed later. Module unload removes the disk first, then flushes and destroys the workqueue before freeing backing memory.

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

The driver maintains lock-free atomic counters for submitted reads and writes, successful bytes transferred, failed read/write requests, and delayed requests. A read-only debugfs view exposes these counters at:

```text
/sys/kernel/debug/faultsimdisk/stats
```

Configuration remains in module parameters under sysfs, while diagnostic statistics live in debugfs.

### Backing store

A spinlock protects concurrent access to the in-memory backing store. Flush completes immediately because there is no volatile hardware cache. Discard and write-zeroes requests clear the corresponding memory range.

## Compatibility

A small compatibility branch handles the `blk_alloc_disk()` API change introduced after Linux 6.8 so CI can compile against Ubuntu 24.04 headers while development runs on newer kernels.
