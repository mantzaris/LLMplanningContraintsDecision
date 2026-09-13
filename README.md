# Validating LLM Planning Constraints Through Decision-Relevant Examples

An implemented finite-domain civilian public-transport research package: typed
constraints, GTFS acquisition/parsing, symbolic planning, independent evaluation,
paired experiment execution, budget guards, and offline replay. See
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
with validation: 31/48 → 33/48, with three recoveries and one deterioration.
The [final annotation/coverage audit](reports/STAGE2_ANNOTATION_COVERAGE_AUDIT.md)
found no clear reference error or unresolved case under the documented conventions;
all 432 rescored outputs retained their categories. Bus-only service, vacuous mode
clauses, and weak visit-order coverage limit generalization. Annotations remain
provisional; the checks are not independent human adjudication.

**Further inference and expansion of the original consequence-weighting method are
paused.** The audit found no material defect warranting a retest. The pilot supports
a small observed benefit from generic validation and reusable infrastructure; it
does not demonstrate a consequence-selection advantage or a positive methodological
contribution. Time normalization remains an engineering baseline. Both final CPU
audits used zero new GPU generations or external model API calls.
See [compact fresh results](artifacts/stage2/pilot-v1),
[figures](artifacts/stage2/pilot-figures), [frozen protocol](docs/stage2-protocol.md),
[provisional annotation review](data/pilot/annotation-review.csv), and
[reproduction commands](docs/stage2-running.md). No further GPU stage is running.
The [historical CPU-only report](reports/STAGE2_CONTROLLED_PILOT.md) and
[earlier access failure](reports/STAGE2_GPU_ACCESS_ATTEMPT_20260912.md) are preserved;
their four historical smoke cases are separate from the fresh pilot.


## Semantic sampling pilot (Stage 3)

The [completed exploratory study](reports/STAGE3_SEMANTIC_SAMPLING_PILOT.md) compared
independent sampling A, generic prompt diversification B, and solver-guided feedback C
on 32 fresh constructed requests, with common time normalization and balanced validation.
At the common final allowance, bounded correct-candidate coverage was **27/32, 31/32,
and 25/32**; ordinary final correctness was **28/32, 28/32, and 25/32**, respectively.
C had zero correctness wins and three losses against each baseline, consumed about
30% more tokens, and found no new correct behavior after the shared first two samples.
The precommitted continuation thresholds were **not met**. Expansion of this feedback
variant is paused; the original consequence-weighting result also remains unchanged.

Oracle diagnostics reached 27/32, 31/32, and 25/32. Judge errors prevented B from
converting all its coverage gains into correct plans. The new infrastructure includes
full/clause signatures, bounded feedback, token admission, paired prefix evaluation,
and exact offline replay. All 32 fresh outputs replayed and 40 tests passed. References
remain provisional, and the bus-only, one-model, one-replicate scope limits generalization.

Stage 3 used **683 actual generations and 1,260.68 measured GPU seconds**, plus ≤60 seconds
uncertainty, including development. All project GPU processes stopped. No further inference
is running or recommended on the evidence of this pilot. See the [frozen protocol](data/sampling/protocol.json),
[method and commands](docs/stage3-semantic-sampling.md), [compact results and figures](artifacts/stage3/pilot-v1),
and [verified raw-artifact storage](artifacts/stage3/pilot-v1/storage.json).
