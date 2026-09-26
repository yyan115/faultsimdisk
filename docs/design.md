# Design

Fault Simulation Disk is a Linux block-device simulator intended for controlled storage failure experiments.

## Stage 1 data path

```text
userspace application
        ↓
filesystem (for example ext4)
        ↓
Linux block layer
        ↓
bio submitted to faultsimdisk
        ↓
read/write against the backing memory
        ↓
bio completion
```

The driver registers one block device, `/dev/faultsim0`. Its capacity is backed by zero-initialized kernel virtual memory. The block layer submits `bio` objects to the driver's `submit_bio` callback. Read and write segments are copied between the bio pages and the backing store.

A spinlock protects the backing store against concurrent data-path access. Flush completes immediately because the backing store has no volatile hardware cache. Discard and write-zeroes requests clear the corresponding memory range.

The implementation intentionally starts with a synchronous data path. Later stages will insert configurable latency and failures before I/O completion, then expose counters and configuration for repeatable experiments.

## Compatibility

The external module targets modern Linux kernels. A small compatibility branch handles the `blk_alloc_disk()` API change introduced after Linux 6.8 so CI can compile against Ubuntu 24.04 headers while development runs on newer kernels.
