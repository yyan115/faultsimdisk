# Contributing

Fault Simulation Disk is a small Linux kernel project. Contributions should stay focused on block I/O simulation, fault injection, observability, testing, and kernel compatibility.

## Development

Use a disposable VM. Never point destructive validation scripts at a real disk.

```bash
make
./scripts/dev.sh load 256
./scripts/dev.sh validate
./scripts/dev.sh unload
```

Before opening a pull request:

- build with the target kernel headers and `W=1`;
- run `shellcheck scripts/*.sh`;
- run the relevant validation scenario in a VM;
- keep compatibility code narrow and documented;
- include measured results only when the environment is stated.

Kernel API changes are expected. If a change is version-specific, include the tested kernel version in the pull request.
