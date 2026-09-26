# Fault Simulation Disk

A Linux kernel block-device simulator for reproducible storage fault testing.

Fault Simulation Disk exposes `/dev/faultsim0` as a normal block device while allowing runtime injection of storage latency and I/O failures.

```text
application / filesystem
        ↓
Linux block layer
        ↓
/dev/faultsim0
        ↓
FaultSimDisk
   ├─ latency injection
   ├─ read/write failure injection
   ├─ I/O statistics
   └─ in-memory backing store
```

## Build and test

Use a disposable Linux VM.

```bash
make
./scripts/dev.sh load
./scripts/dev.sh smoke
./scripts/dev.sh fault-test
./scripts/dev.sh stats-test
./scripts/dev.sh stats
./scripts/dev.sh unload
```

## Runtime controls

```bash
./scripts/dev.sh set latency_ms 100
./scripts/dev.sh set read_fail_pct 5
./scripts/dev.sh set write_fail_pct 10
./scripts/dev.sh config
```

## Runtime statistics

```bash
./scripts/dev.sh stats
```

The debugfs stats view reports read/write requests and bytes, failed reads/writes, delayed requests, and the active fault configuration.

## Roadmap

- [x] Functional Linux block device
- [x] Read/write path and in-memory backing store
- [x] Configurable latency injection
- [x] Configurable read/write failure injection
- [x] Runtime statistics and observability
- [ ] `fio` and application resilience scenarios

See [design notes](docs/design.md) for the architecture.
