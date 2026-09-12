# Validating LLM Planning Constraints Through Decision-Relevant Examples

Stage 1: a finite-domain civilian public-transport research implementation. See
[methodology](docs/methodology.md), [data provenance](docs/data.md), and
[Stage 1 evidence and limitations](docs/stage1-report.md).

Python 3.11–3.12; development verified with Python 3.11. The default install is CPU only.
Install [uv](https://docs.astral.sh/uv/) and run `uv sync --frozen --extra dev`.

Commands and reproduction details are in [the run guide](docs/running.md).
Raw agency schedules, model weights, and caches are excluded from Git. This is an
unofficial research project, unaffiliated with and not endorsed by TriMet. Requests
and annotations are constructed, provisional development material; schedules are
published services, not observed vehicle movements. The repository MIT license
does not relicense agency data or model weights.


## Controlled feasibility pilot (Stage 2)

The [fresh Stage 2 GPU report](reports/STAGE2_GPU_EXECUTION.md) records a completed
48-base paired pilot. The frozen throughput rule selected one replicate before
judging. **D and E each resolved 33/48 correctly**, with different witness sequences
in 2/48 cases and no correctness wins or losses. CPU oracle replay reached 35/48 for
both. The run used 358 generations and 681.62 measured GPU seconds; all 48 pairs
replayed exactly. No consequence-selection advantage was demonstrated.

The [CPU mechanism diagnosis](reports/STAGE2_MECHANISM_DIAGNOSIS.md) compares budget 0
with validation: 31/48 → 33/48, with three recoveries and one deterioration. It explains
the rare selector divergence and recommends an annotation and data-coverage gate
before further inference. No new GPU work was used for that diagnosis.
See [compact fresh results](artifacts/stage2/pilot-v1),
[figures](artifacts/stage2/pilot-figures), [frozen protocol](docs/stage2-protocol.md),
[provisional annotation review](data/pilot/annotation-review.csv), and
[reproduction commands](docs/stage2-running.md). No further GPU stage is running.
The [historical CPU-only report](reports/STAGE2_CONTROLLED_PILOT.md) and
[earlier access failure](reports/STAGE2_GPU_ACCESS_ATTEMPT_20260912.md) are preserved;
their four historical smoke cases are separate from the fresh pilot.
