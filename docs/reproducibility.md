# Reproducibility and evidence

Fault Simulation Disk separates reproducible functional claims from environment-specific performance observations.

## What is reproducible

The hosted validation checks properties that should hold across machines:

- a configured fixed latency materially delays I/O by the requested interval within scheduler tolerance;
- 100% read/write failure policies reject the corresponding I/O;
- ext4 formats, mounts, writes, syncs, and reads back through `/dev/faultsim0`;
- SQLite and PostgreSQL surface injected lower-level write failures;
- database and `fio` tests compare baseline behavior with injected faults instead of requiring one absolute throughput number.

Absolute baseline IOPS are not treated as portable performance claims because CPU, virtualization, kernel, and host load affect them.

## Independent hosted execution

The `Runtime Integration` GitHub Actions workflow runs on a fresh GitHub-hosted Ubuntu VM. It:

1. captures the commit, runner image, kernel, architecture, compiler, and test-tool versions;
2. builds the module against the runner's own kernel;
3. loads `/dev/faultsim0`;
4. runs the full ext4, fault injection, statistics, `fio`, SQLite, and PostgreSQL validation suite;
5. renders structured JSON, Markdown, and SVG results;
6. uploads the raw output and hashes as a workflow artifact;
7. publishes the latest verified report to the `validation-results` branch.

The README embeds the generated SVG card from that branch, so the repository front page reflects the latest successful hosted validation without bot commits to `main`.

## Evidence integrity

Each hosted run packages the raw environment, full validation output, hashes, and generated report into `runtime-evidence.tar.gz`. Public runs create a GitHub artifact attestation for that archive using Sigstore.

To verify a downloaded evidence archive:

```bash
gh attestation verify runtime-evidence.tar.gz -R yyan115/faultsimdisk
```

The attestation cryptographically binds the artifact digest to the repository, workflow identity, triggering event, and commit SHA. It establishes provenance and integrity; it does not prove that the test logic itself is correct. The workflow and validation scripts remain public and reviewable for that reason.

## Release snapshots

Tagged releases rerun hosted validation from the tagged commit. The GitHub Release includes:

- source archive and SHA-256 checksum;
- the exact validation Markdown and JSON;
- raw runtime evidence and hashes;
- attestations for both the source archive and runtime evidence.

This gives each version a frozen validation record, while the `validation-results` branch represents the latest successful hosted run for relevant code or test changes.

## Local testing

Local VM runs remain useful for development and compatibility checks against specific Linux versions. They are supplementary evidence rather than the primary trust mechanism.
