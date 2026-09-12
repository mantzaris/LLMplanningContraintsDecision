# Stage 2 artifact index

The current result is [pilot-v1](pilot-v1/summary.json): **48 fresh base requests,
one replicate under the frozen timing rule**. D and E both resolve 33/48 correctly;
oracle replay reaches 35/48 for both. Two witness sequences differ and no correctness
outcomes differ. See the [execution report](../../reports/STAGE2_GPU_EXECUTION.md).

- `pilot-v1/`: compact fresh results, independent diagnostic traces, run/source hashes,
  verified replication records, replay checks and completed cumulative GPU accounting.
- `pilot-figures/`: four fresh comparison figures, each PDF/SVG/PNG.
- `prior-reanalysis/` and `figures/`: historical four-case Stage 1 reanalysis only.
- `execution-attempt-20260912/`: immutable pre-GPU access diagnosis, annotation checks
  and local-preservation inventory from the earlier blocked attempt.
- Root-level `fresh-pilot-status.json`, `gpu-accounting.json`, `gpu-access.json`, and
  other earlier records are **historical CPU-delivery snapshots**. They are preserved
  unchanged; their pending/zero-usage status is superseded by `pilot-v1/`.

Full timetables and prompts are excluded from Git under the project's reuse policy.
The fresh GPU archive, prior local-only archive, and offline analysis/oracle/replay
archive now have verified copies on the established persistent pod volume. Their
paths and checksums are in the fresh replication records. This is not an independent
off-provider backup. CPU reproduction commands are in the run guide.
