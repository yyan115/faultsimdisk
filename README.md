# Fault Simulation Disk

A Linux kernel block-device simulator for reproducible storage fault testing.

**Current stage:** functional in-memory block device. Fault injection and observability come next.

```text
application / filesystem
        ↓
Linux block layer
        ↓
/dev/faultsim0
        ↓
FaultSimDisk driver
        ↓
in-memory backing store
```

## Build and test

Use a disposable Linux VM for development.

```bash
make
./scripts/dev.sh load
./scripts/dev.sh smoke
./scripts/dev.sh logs
./scripts/dev.sh unload
```

The smoke test formats `/dev/faultsim0` as ext4, mounts it, writes a file, syncs it, and reads the data back.

The device size defaults to 64 MiB and can be selected at load time:

```bash
sudo insmod faultsimdisk.ko size_mb=128
```

## Roadmap

- [x] Functional Linux block device
- [x] Read/write path and in-memory backing store
- [ ] Configurable latency injection
- [ ] Configurable I/O failure injection
- [ ] Runtime statistics and observability
- [ ] `fio` fault and performance scenarios

See [design notes](docs/design.md) for the architecture.
