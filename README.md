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
   └─ in-memory backing store
```

## Build and test

Use a disposable Linux VM.

```bash
make
./scripts/dev.sh load
./scripts/dev.sh smoke
./scripts/dev.sh fault-test
./scripts/dev.sh unload
```

## Runtime fault controls

```bash
./scripts/dev.sh set latency_ms 100
./scripts/dev.sh set read_fail_pct 5
./scripts/dev.sh set write_fail_pct 10
./scripts/dev.sh config
```

Settings affect new I/O requests and can be changed while the module is loaded. Latency is bounded to 0-5000 ms; failure rates are 0-100%.

## Roadmap

- [x] Functional Linux block device
- [x] Read/write path and in-memory backing store
- [x] Configurable latency injection
- [x] Configurable read/write failure injection
- [ ] Runtime statistics and observability
- [ ] `fio` and application resilience scenarios

See [design notes](docs/design.md) for the architecture.
