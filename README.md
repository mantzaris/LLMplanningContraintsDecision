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

The [Stage 2 report](reports/STAGE2_CONTROLLED_PILOT.md) records a frozen 48-request,
paired balanced-versus-consequence pilot, prefix budgets 0/1/2/4, a separate oracle
replay, and reproducible analysis/figures. **Fresh GPU execution is blocked:** the
supplied SSH gateway cannot reach its pod. Stage 2 generated no new model outputs.
A labeled CPU reanalysis of the four previous smoke requests gives D = E = 2/4 correct,
with no distinguishing witnesses and no oracle improvement; it is not the fresh pilot.
See [protocol](docs/stage2-protocol.md), [annotation review](data/pilot/annotation-review.csv)
and [exact reproduction/resume commands](docs/stage2-running.md). The research conclusion
is inconclusive, with no demonstrated selection advantage.
