# Stage 1 report — 2026-09-12

The executable foundation is implemented and has run on the provided GPU. The
smoke evidence does **not** establish a benefit from consequence-based selection.
It exposes shared translation errors and weak judgment explanations that must be
addressed before a larger pilot. No held-out experiment or policy tuning occurred.

## Repository and implemented functionality

Initial revision: `aec08b6ce05c4fdffcfa7dcafbdfcc8f7b390132`. The working tree was
clean on `main`, with only an MIT license, no implementation/dependencies, and no
applicable `AGENTS.md`. Development stayed on `main`; no feature branch, worktree,
PR, force push or history rewrite was used. Existing project infrastructure was
absent, so Stage 1 establishes the installable `plancheck` package and locked
Python 3.11–3.12 environment.

Working components include frozen public-feed acquisition; calendar-aware GTFS
parsing and conservative scheduled connections; public pool construction; typed
constraint AST and strict JSON parsing; deterministic Z3 planning; independent
reference evaluation; structural and finite-semantic deduplication; exact witness
generation; balanced and weighted selectors; isolated model judgment; bounded
critique/repair; functional A–E methods; separate gold diagnostics; grouped
development/reference data and human-review export; GPU/request guards; immutable
run records, cache attribution, CPU replay, evaluation and audit/report commands.

Methodology and baseline adaptations are in [methodology.md](methodology.md).
[literature.md](literature.md) and [references.bib](references.bib) verify the starting
references and targeted newer overlap. The claim is limited to the proposed
decision-consequence weighting policy, not generic LLM+solver or counterexample
validation machinery.

## Data acquired and bounded

TriMet's published ZIP was downloaded on 2026-09-12 (completion 15:07:08 UTC),
29,521,107 bytes, SHA-256
`82e6b822de008367b3d3d35bb52545807ea41b6f56623a9aa4b1162b3d54671b`.
Feed version `20260823-20260910-0900` declares validity 2026-08-23–2027-02-27;
calendar rows actually stop at 2026-11-28. The chosen service day is 2026-09-14,
07:00–10:00, `America/Los_Angeles`.

Pre-model coverage rules selected connected downtown bus routes 2, 4 and 17,
70 named stop/call IDs and 6,574 ride edges. Public limits are two boardings per
segment, 120 seconds for a same-stop connection, 64 deterministically sampled paths
per segment and at most 256 combined journeys. Smoke pools contain 64 one-way and
256 two-segment journeys. Feasibility, optimality and equivalence remain conditional
on the pool. All methods use identical public pools.

There are 60 assistant-authored requests: six base groups × five requirement
variants × two modest textual forms. Groups 00–03 are development, 04 validation,
05 held out. Only four `p0` requests in development group 00 were run. Related
variants remain grouped; routes, geography and dates overlap across splits. The
annotations are provisional, independently specified and not human-audited.
Requests are not real passenger data, and schedules are not observed vehicle
movements. See [data.md](data.md) for provenance and supported transport behavior.

The repository includes acquisition manifests, constructed requests, annotations
and the review CSV. Raw/derived agency schedules and full prompts remain local
under the documented TriMet reuse policy. Historical availability at the mutable
public URL is not guaranteed; exact reproduction needs the retained checksum-frozen
ZIP or full local run snapshots. No weights or caches are committed.

## Deterministic verification

The final focused suite passed **24 tests** on Python 3.11.13, including:

- Exhaustive finite-fixture prediction/reference/Z3 agreement for timing boundaries,
  modes, transfers, ordered calls and negation; conjunction and directional scope.
- Injected omissions, incorrect negation and outbound/return confusion; SAT,
  infeasibility and forced solver unknown/deadline outcomes.
- Semantic deduplication, distinguishing-witness validity, cross-violation scores,
  positive cost normalization and deterministic ties.
- All A–E paths using explicitly scripted diagnostic outputs, repair success and
  damage, uncertain/contradictory labels, cache costs and failed-attempt retention.
- Persistent GPU request limits, elapsed-time limits, crashed-session reservation,
  completed-output resume, changed-config rejection and held-out rejection.
- Public-only judgment prompts, ordinary gold-mode rejection and import boundaries.
- Synthetic and actual frozen GTFS calendar exceptions and post-midnight times,
  pickup/drop-off restrictions, minimum connections, prohibitions and DST origin.

Ruff checks pass. A separate explicitly injected gold diagnostic ran and is retained
in [gold-diagnostic.json](../artifacts/stage1/gold-diagnostic.json); both selectors
chose the same witnesses in this fixture, with different verified numeric weights.
This is logic evidence, not model performance. Historical-source CPU replay matched
all 20 saved outputs for each of the three GPU passes (60 output comparisons).

## Actual GPU evidence and accounting

RunPod access succeeded via an interactive PTY/stdin shell. The specified named
identity was absent locally, but available SSH authentication was accepted by the
gateway. A non-PTY probe failed and remote command arguments were ignored, so file
transfer used base64 over shell stdin. No direct endpoint was invented. The GPU
was idle before loading; unrelated jobs and the rented pod were left alone.

Hardware: NVIDIA RTX PRO 6000 Blackwell Server Edition, 97,887 MiB total memory,
driver 595.91.07. Runtime: Python 3.12.3, PyTorch 2.8.0+cu128, Transformers 4.51.3,
BF16, no quantization. A suitable cached **Qwen2.5-7B-Instruct** was reused read only.
All four weight shards matched official SHA-256 values and all tokenizer/config
and license files matched the Git blob identities of revision
`a09a35458c702b33eeacc393d103063234e8bc28` (Apache-2.0).

Parameter devices were exclusively `cuda:0`; generated output tensors were on
`cuda:0`; `nvidia-smi` observed project Python processes using GPU memory. Peak
PyTorch allocated memory was 15,986,949,120 bytes. The model emitted an SDPA sliding
window warning, but its verified configuration has `use_sliding_window=false`.
Inherited sampling fields and installed packages are recorded in
[runtime.json](../artifacts/stage1/runtime.json). No CPU inference fallback occurred.

| Preserved pass | Purpose | New generations | GPU-resident seconds | Execution revision |
|---|---|---:|---:|---|
| v1 | Original interface; all candidate parses failed | 20 | 92.86 | `4a644e969eb43bcf74534c0b55a26759986219ff` |
| v2 | Explicit node example and schema; same requests/policies | 25 | 94.01 | `fb4258c9e22e03abae683194edbf31349e2113db` |
| v3 | Accept complete JSON fences; reuse v2 text; one newly needed repair | 1 | 50.52 | `3991b821c0c5778156250ea7ed6516839d6bf9b7` |
| **Total** | No separate warm-up calls | **46** | **237.39** | |

Total model-resident time is **0.06594 aggregate GPU-hours**. Adding a conservative
30-second overhead allowance gives 267.39 seconds (0.07428 hours), still far below
one hour. All 46 attempts are charged, including semantically/structurally failed
outputs; there were no backend generation failures. Model loading, generation and
disposal are included. Final GPU inspection showed **0 MiB, 0% utilization and no
compute processes**. Project inference processes exited; the pod was not terminated.

The [GPU ledger](../artifacts/stage1/gpu-accounting.json) records all sessions and
attempts. Total actual generation output was 6,246 tokens from 83,630 input tokens.
Generation calls took 90.36 seconds in aggregate (about 69.1 output tokens/second,
including prompt processing in that denominator); loading took about 47–49 seconds
per pass. Cached calls retain independent logical attribution. Full run outputs,
prompts, errors and unsuccessful attempts are in local `runs/smoke-v1`, `v2`, `v3`.

## Observed smoke results, including failures and ties

The automatically generated final table is
[smoke-v3-table.md](../artifacts/stage1/smoke-v3-table.md); compact audits of all
passes are [v1](../artifacts/stage1/smoke-v1.json), [v2](../artifacts/stage1/smoke-v2.json)
and [v3](../artifacts/stage1/smoke-v3.json). These are development integration
evidence, not a population estimate. Four related requests form only one base group;
no confidence interval is reported.

| Method | Satisfied returned plans / 4 | False infeasibility | Unresolved | Logical calls |
|---|---:|---:|---:|---:|
| A | 2 | 1 | 4 | 4 |
| B | 2 | 0 | 4 | 8 |
| C (SSV adaptation) | 2 | 0 | 2 | 10 |
| D (balanced adaptation) | 2 | 1 | 4 | 16 |
| E (consequence) | 2 | 1 | 4 | 16 |

No invalid returned plan or damaged correct plan was observed in this small model
sample; harmful repair is exercised only in the injected tests. A correct plan
can still be semantically unverified, so satisfaction and unresolved counts are
different dimensions. Diagnostic fallback plans are retained but not counted as
returned solutions.

- **Structured translations:** v1 confused `kind` and `op`. V2/v3 yielded valid
  formulas on timing, negation and scope requests. The genuinely contradictory
  request was incorrectly labeled unsupported by all sampled candidates.
- **Natural errors:** the model translated 08:15 as 29,400 seconds (08:10). That
  error happens to be equivalent on this tiny pool. It translated 09:15 as 54,900
  seconds (15:15), causing false infeasibility despite two reference-feasible plans.
  These errors were not injected. The candidate classes shared them.
- **Meaningful candidate disagreements:** none in the GPU sample. On each of the
  three parseable requests, all four D/E samples collapsed to one pool-semantic
  class. On the contradictory request there were no supported candidates.
- **Distinguishing witnesses:** exact witnesses and weights passed CPU fixture
  tests. D/E had no natural distinguishing witness to send to the GPU judge.
- **Source-based judgments:** five concrete C judgments parsed after the fence
  correction, and their labels matched provisional independent annotations 5/5.
  Explanations were unreliable: one claimed rail use in the all-bus pool and another
  misstated transfers. Spans often pointed to generic request text. Thus successful
  structured judgments do not establish faithful explanations or a reliable oracle.
- **Repair/unnecessary work:** C's positive/negative checks did not improve the
  two already correct plans. Its scope check exposed disagreement with the false
  infeasibility interpretation, eliminated it, and attempted one repair; the repair
  still contradicted the judgment, so the output remained explicitly unresolved.
  B also failed to recover the scope case. No hidden labels chose replacements.
- **D versus E:** exact tie in candidate classes, final decisions and logical cost.
  Extra samples were unnecessary for these decisions. The sample does not test
  consequential witness selection empirically and provides no evidence of advantage.

The format fixes were interface repairs, recorded before each rerun, on the same
predeclared subset. No scenario, score, objective, candidate count or budget was
changed to favor a method. Earlier failures remain separately reported.

## Remaining limitations and next-stage decision

The implementation is suitable for a **small repair gate**, but the evidence does
not justify expanding to a publication-scale or larger pilot yet. Specific needs:
review source/reference annotations; improve exact time conversion and the model's
distinction between contradictory and unsupported requests; verify judge explanations
and spans; and assess whether natural candidate diversity exists on additional
development groups. Candidate diversity must be measured, not manufactured by
mixing injected corruptions into the principal experiment. Freeze the weighted
policy and retain a no-disagreement stratum.

Coverage remains bus-only, one service day and a sampled finite universe. Multimodal,
walking/through-service, accessible journeys and real passenger intent are unvalidated.
Reference annotations and judgments are unaudited. The public feed is not an
immutable public archive. Full schedule-containing run redistribution needs a
separate rights decision. No TravelPlanner environment or held-out model run was
needed for Stage 1.

After those repairs and explicit authorization for the next stage, use the frozen
four-request group-01 gate in `configs/next-gate.json`:

```bash
uv sync --frozen --extra dev
uv run --frozen --extra dev plancheck cpu-check
# On the already inspected GPU environment, after installing the gpu extra:
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 timeout --signal=TERM --kill-after=10s 3300s \
  uv run --frozen --extra gpu plancheck smoke --config configs/next-gate.json \
  --public data/prepared/public --run runs-next-stage/gate \
  --model-path /absolute/path/to/verified/cached/model
uv run --frozen plancheck evaluate --run runs-next-stage/gate \
  --references data/references/provisional.json
uv run --frozen plancheck report --run runs-next-stage/gate \
  --output runs-next-stage/gate-report.md
```

The new stage directory is for a separately authorized stage, not a way to reset
the Stage 1 ledger. The gate retains the 100-call/one-hour guards and should need
roughly 2–5 GPU minutes at the observed throughput; allow 10 minutes for longer
judgments and loading. This is a forecast, not a measured new experiment.

If the gate succeeds, design a 30-independent-base pilot with two textual variants
and two generation replicates, grouped analysis and manually reviewed references.
D/E would use 1,680 logical calls at the current per-method upper bound, at most
about 1,200 actual calls with shared translations and no shared judgments/repairs.
At about 2 seconds per observed call this is roughly 40 minutes plus loading;
budget **2 GPU-hours provisionally** for longer prompts, larger outputs and retries.
That pilot needs its own explicit budget authorization and a versioned runner limit;
Stage 1 cannot launch it. Publication-scale held-out work follows only after a
separate protocol freeze and uncertainty-aware pilot assessment.
