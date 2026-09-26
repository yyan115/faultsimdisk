## Summary

Describe the change and the storage/kernel behavior it affects.

## Validation

- [ ] `make` succeeds with `W=1`
- [ ] `shellcheck scripts/*.sh` passes
- [ ] Relevant VM validation was run
- [ ] Documentation was updated if behavior changed

## Kernel safety

- [ ] No test was run against a non-disposable block device
- [ ] Module unload/cleanup behavior was considered
