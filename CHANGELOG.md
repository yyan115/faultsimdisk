# Changelog

## Unreleased

### Fixed

- Advertise DISCARD and WRITE_ZEROES queue capabilities so the implemented handlers are reachable through normal block-device operations.
- Harden validation scripts against an unexpected `/dev/faultsim0` device node.

### Changed

- Validate DISCARD and WRITE_ZEROES behavior in the hosted runtime suite.
- Capture the actual userspace errors from deterministic raw read/write failure injection.
- Suppress SQLite setup noise from raw validation evidence.
- Rework the README and generated live report around fault propagation and automatically sourced evidence.
- Restrict privileged runtime integration to trusted `main` pushes and manual dispatches; pull requests continue to use read-only build and DKMS CI.
- Restore the release workflow to tag-only publication after the initial automated release bootstrap.
- Clarify DKMS installation prerequisites.

## 1.0.1 - 2026-09-26

### Fixed

- Drain timer-pending delayed I/O before destroying the workqueue during module unload.
- Bound discard and write-zeroes lock hold time by zeroing the backing store in page-sized chunks.

### Changed

- Removed unused HTML report generation and stale development-stage wording.
- Corrected release, validation, and reproducibility documentation after the v1.0 audit.

## 1.0.0 - 2026-09-26

### Added

- Linux block device exposed as `/dev/faultsim0`.
- Runtime latency injection and independent read/write failure rates.
- Deferred I/O completion through a dedicated workqueue.
- Atomic runtime statistics through debugfs.
- ext4, raw-I/O, `fio`, SQLite, and PostgreSQL validation scenarios.
- GitHub-hosted runtime validation with generated Markdown, JSON, SVG, raw evidence, and Sigstore-backed artifact attestations.
- DKMS installation support.
- Automated tagged releases with source archives, checksums, validation evidence, and attestations.
- Compatibility support across the `blk_alloc_disk()` API change after Linux 6.8.
