---
layout: default
title: Fault Simulation Disk
---

# Fault Simulation Disk

A Linux kernel block-device simulator for reproducible storage fault testing.

Fault Simulation Disk exposes `/dev/faultsim0` as a real Linux block device and lets tests inject latency or I/O errors without failing physical storage.

## What it tests

- filesystems such as ext4;
- raw block workloads through `fio`;
- embedded databases through SQLite;
- durable WAL-backed database behavior through PostgreSQL;
- application-visible propagation of lower-level storage failures.

## Data path

```text
application / database
        ↓
filesystem
        ↓
Linux block layer
        ↓
/dev/faultsim0
        ↓
FaultSimDisk
   ├─ latency injection
   ├─ I/O failure injection
   ├─ runtime statistics
   └─ in-memory backing store
```

## Recorded validation

On Ubuntu 26.04 with Linux 7.0.0-34, a 4 KiB QD1 random-read run measured **518,012.5 IOPS baseline** and **47.5 IOPS with 20 ms injected latency**. A SQLite full-synchronous transaction increased from **6 ms to 262 ms** with 50 ms storage latency.

These are environment-specific validation results, not hardware performance guarantees.

- [Design](design.md)
- [Validation](validation.md)
- [Repository](https://github.com/yyan115/faultsimdisk)
