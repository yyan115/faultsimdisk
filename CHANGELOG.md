# Changelog

## Unreleased

### Added

- PostgreSQL durable-commit and write-failure validation scenario.
- DKMS installation support.
- Automated tagged source releases.
- CI artifacts and DKMS build validation.
- GitHub Pages-ready project documentation.

## 1.0.0

- Linux block device exposed as `/dev/faultsim0`.
- Runtime latency injection and independent read/write failure rates.
- Deferred I/O completion through a dedicated workqueue.
- Atomic runtime statistics through debugfs.
- ext4, raw-I/O, fio, and SQLite validation scenarios.
- Compatibility support across the `blk_alloc_disk()` API change after Linux 6.8.
