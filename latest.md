# Fault Simulation Disk test results

**Overall status: PASS**

Generated from the validation output for the commit and GitHub Actions run below.

## What happened

| Scenario | Fault injected | What the workload observed | Status |
| --- | --- | --- | --- |
| ext4 filesystem | None | Format → mount → write → sync → read back | PASS |
| DISCARD / WRITE_ZEROES | None | Queue advertises both operations and both ranges read back as zero | PASS |
| Raw block read | +100 ms latency | 112 ms end-to-end read latency | PASS |
| Raw block read | 100% read failure | `dd: IO error: Input/output error` | PASS |
| Raw block write | 100% write failure | `dd: IO error: Input/output error` | PASS |
| fio 4 KiB QD1 random read | +20 ms latency | 472,151.9 → 47.5 IOPS | PASS |
| SQLite FULL-sync transaction | +50 ms latency | 4 → 260 ms | PASS |
| SQLite FULL-sync transaction | 100% write failure | `Error: stepping, disk I/O error (10)` | PASS |
| PostgreSQL synchronous commit | +50 ms latency | 8 → 59 ms | PASS |
| PostgreSQL synchronous commit | 100% write failure | `PANIC:  could not fdatasync file "000000010000000000000001": Input/output error` | PASS |
| debugfs accounting | Mixed workload | Requests, bytes, failures, and delayed I/O recorded | PASS |

## Provenance

| Field | Value |
| --- | --- |
| Commit | [15698484db48](https://github.com/yyan115/faultsimdisk/commit/15698484db48e74ed044cf56a14abb2fc3cf652b) |
| GitHub Actions run | [#36301623952](https://github.com/yyan115/faultsimdisk/actions/runs/36301623952) |
| Runner | ubuntu26 20260920.143.1 |
| Kernel | 7.0.0-1012-azure |
| Architecture | x86_64 |
| fio | fio-3.41 |
| SQLite | 3.46.1 |
| PostgreSQL | 18.6 (Ubuntu 18.6-1.pgdg26.04+2) |

Generated at 2026-09-27T06:58:23+00:00. Performance measurements depend on the runner and kernel listed above.
