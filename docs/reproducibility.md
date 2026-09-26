# Reproducibility and evidence

Fault Simulation Disk separates functional claims from environment-specific performance observations.

## Reproducible claims

The validation suite checks properties that should hold across machines:

- configured fixed latency delays I/O by at least the requested interval within scheduler tolerance;
- 100% read/write failure policies reject the corresponding I/O;
- ext4 formats, mounts, writes, syncs, and reads back through `/dev/faultsim0`;
- database tests compare baseline behavior with injected faults instead of requiring one absolute throughput result.

Absolute baseline IOPS are not portable performance claims because CPU, virtualization, kernel, and host load affect them.

## Independent execution

GitHub Actions includes a runtime integration job on a fresh GitHub-hosted Ubuntu VM. It builds the module against the runner kernel, loads it, runs the filesystem smoke test, and uploads environment metadata tied to the commit SHA.

Local Multipass runs remain useful for Linux 7.0 compatibility testing, but they are development evidence rather than the primary trust mechanism.

## Provenance

When the repository is public, GitHub artifact attestations can cryptographically bind release and validation artifacts to the repository, workflow, triggering event, and commit that produced them.

Attestation proves provenance and integrity, not semantic correctness. The workflow and test scripts remain reviewable source code so reviewers can inspect what was actually executed.
