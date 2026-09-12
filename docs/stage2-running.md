# Reproducing and resuming Stage 2

Use Python 3.11 or 3.12 and the committed `uv.lock`. The local verified environment
uses Python 3.11.13; the earlier GPU environment used Python 3.12.3. Run these commands
from the repository root. The Stage 2 report distinguishes the unrun fresh pilot from
the completed historical CPU reanalysis.

## CPU environment and fresh data

```bash
uv sync --frozen --extra dev --extra analysis
uv run --frozen --extra dev plancheck cpu-check
uv run --frozen plancheck pilot-prepare --config configs/data.json \
  --feed data/raw/trimet-82e6b822de008367b3d3d35bb52545807ea41b6f56623a9aa4b1162b3d54671b.zip \
  --prior-public data/prepared/public/scenarios.json --output data/prepared/stage2
uv run --frozen plancheck pilot-review --public data/prepared/stage2/public \
  --references data/prepared/stage2/private/references.json \
  --output data/prepared/stage2/private/automated-review.json
```

The preceding Stage 1 `prepare --config configs/data.json --feed ...` command creates
`data/prepared/public/scenarios.json` if needed. Acquisition of today's agency ZIP
does not guarantee the frozen historical checksum; use the retained ZIP or public
snapshots. The preparation command never silently accepts a replacement feed.

The protocol has already been frozen and committed. Do not overwrite it or refreeze
it after looking at comparative results. To review the provenance of that operation,
the command used before protocol commit `1aa2ad1` was:

```bash
uv run --frozen plancheck pilot-freeze --config configs/pilot.json \
  --prepared data/prepared/stage2 --output data/pilot
```

Its parent revision and source hash are historical records, so rerunning that command
from a later commit intentionally refuses to overwrite the immutable protocol. Data
and wording checks can be repeated without refreezing the research protocol.

## Authorized GPU execution after connectivity is restored

No new GPU run was possible in this stage. Keep connection settings local and reuse
the user's normal SSH authentication. The provided gateway accepts an interactive
PTY; command arguments after the SSH target may be ignored. Inspect hardware, memory,
storage, process names and model cache after an actual remote shell prompt. Do not
use a different pod or invent a direct TCP endpoint. The prior verified isolated paths
were `/workspace/LLMplanningConstraintsStage1/.venv` for the environment and
`/workspace/AgentRobustComms/stage2/model` for the read-only model cache. Recheck them;
the Stage 2 connection attempts could not verify their current availability.

For code and public-data transfer, make an archive/bundle locally and use the existing
stdin/base64 helper. Set `RUNPOD_TARGET` privately to the supplied SSH target; it is
not a committed setting. The data archive contains only public inference inputs.
The code bundle also contains committed annotation exports; the ordinary runtime
does not read those files:

```bash
git bundle create /tmp/plancheck-stage2.bundle main
tar -czf /tmp/plancheck-stage2-public.tar.gz -C data/prepared/stage2 public
python3 scripts/ssh_transfer.py --identity ~/.ssh/id_rsa --target "$RUNPOD_TARGET" \
  --local /tmp/plancheck-stage2.bundle \
  --remote-root /workspace/LLMplanningConstraintsStage2 --remote-name project.bundle
python3 scripts/ssh_transfer.py --identity ~/.ssh/id_rsa --target "$RUNPOD_TARGET" \
  --local /tmp/plancheck-stage2-public.tar.gz \
  --remote-root /workspace/LLMplanningConstraintsStage2 --remote-name public.tar.gz
```

After obtaining the remote interactive shell, use a fresh isolated Stage 2 directory.
A bundle clone is a transport copy on `main`, not a feature branch or Git worktree.
On subsequent resumes, reuse the same clone and the same `runs/stage2-gpu-budget.jsonl`:

```bash
cd /workspace/LLMplanningConstraintsStage2
git clone --branch main project.bundle project
cd project
tar --no-same-owner -xzf ../public.tar.gz
/workspace/LLMplanningConstraintsStage1/.venv/bin/python -m plancheck.cli \
  gpu-diagnostic --output runs/stage2-before.json
```

If the reused environment still points its editable package at the old Stage 1 clone,
set `PYTHONPATH="$PWD/src"` for the commands below (and the diagnostic above) or install
the package into a separate Stage 2 venv. Do not change the other project's environment.
The GPU optional dependencies and model file identities must match the recorded
metadata; the runner rejects a mismatch and never falls back to CPU inference.

```bash
PYTHONPATH="$PWD/src" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  timeout --signal=TERM --kill-after=10s 7180s \
  /workspace/LLMplanningConstraintsStage1/.venv/bin/python -m plancheck.cli pilot-run \
  --config configs/pilot.json --public public --run runs/stage2-pilot-v1 \
  --model-path /workspace/AgentRobustComms/stage2/model
```

For a newly installed isolated environment, use `uv sync --frozen --extra gpu` and
`uv run --frozen --extra gpu plancheck pilot-run ...` instead, after checking CUDA and
hardware compatibility. The local source path must identify the Stage 2 implementation.
There is no need to redownload weights when the existing read-only cache still matches.

The first four bundles are the included candidate-only timing diagnostic. The runner
writes `scope.json` before judging, selecting two replicates, one replicate, or fewer
six-base blocks according to the frozen timing rule. It checkpoints complete pairs,
keeps unsuccessful attempts and attributes cached costs independently to each method.
The project model is disposed in `finally`; do not terminate the pod or unrelated jobs.
A crash reserves the entire outstanding budget conservatively. Never move a run to
another ledger or reset the journal to recover that budget. A fresh shell probe is not
proof of CUDA inference; require parameter/device evidence, GPU process/memory evidence
and a successful generation in the actual run artifacts.

## Saved-output replay, independent evaluation and plots

The completed corrected historical reanalysis used these exact commands:

```bash
uv run --frozen plancheck pilot-history --run runs/smoke-v3 --output runs/stage2-history-v2
uv run --frozen plancheck pilot-analyze --run runs/stage2-history-v2 \
  --public runs/stage2-history-v2/inputs --references data/references/provisional.json \
  --output runs/stage2-history-analysis-v2
uv run --frozen python scripts/replay_revision.py --run runs/stage2-history-v2 \
  --output runs/stage2-history-replay-v2
uv run --frozen --extra analysis plancheck pilot-figures \
  --analysis runs/stage2-history-analysis-v2 --output artifacts/stage2/figures \
  --label 'Stage 1 saved-output reanalysis: 4 requests, 1 OD group; no fresh pilot'
uv run --frozen python scripts/export_stage2.py --run runs/stage2-history-v2 \
  --analysis runs/stage2-history-analysis-v2 --output artifacts/stage2/prior-reanalysis
uv run --frozen --extra analysis python scripts/stage2_timeline.py \
  --public runs/stage2-history-v2/inputs --references data/references/provisional.json \
  --run runs/stage2-history-v2 --output artifacts/stage2/figures
```

For a new reanalysis identity, use the recorded source revision `df7c5b2` through
`replay_revision.py` for exact historical replay. `pilot-history` manifests intentionally
record the current code revision, so invoking it against an existing identity after
code changes refuses a mismatch. Do not delete unsuccessful v1 records. The `v2`
results and four-pair replay verification are retained locally; compact results can
regenerate the four comparison plots without the full schedule snapshots.

After an eventual fresh pilot, copy its full run directory to the established durable
experiment storage and local analysis area through the verified stdin mechanism.
Pass reference files only to the separate offline analysis command; they are never
ordinary runtime inputs. Then run:

```bash
uv run --frozen python scripts/replay_revision.py --run runs/stage2-pilot-v1 \
  --output runs/stage2-pilot-replay-v1
uv run --frozen plancheck pilot-analyze --run runs/stage2-pilot-v1 \
  --public data/prepared/stage2/public --references data/pilot/references.json \
  --output runs/stage2-pilot-analysis-v1
uv run --frozen --extra analysis plancheck pilot-figures \
  --analysis runs/stage2-pilot-analysis-v1 --output artifacts/stage2/pilot-figures \
  --label 'Controlled feasibility pilot: development requests, provisional references'
```

`pilot-analyze` creates an explicitly separate oracle output tree and reference-coverage
annotations. It never chooses the ordinary output with those labels. Missing pairs,
unknown failed-call token counts and incomplete full-sample bounds remain visible.
Ordinary run artifacts contain raw prompts, candidate bundles, scored witnesses,
judgments, repairs, backend/settings and logical costs; the stage journal separately
accounts actual GPU time and attempts. Do not add reused budget-prefix costs together
as though they were separately executed experiments.

Current Stage 2 raw artifacts have not been copied to the unreachable pod. They remain
locally under ignored `runs/` and `data/prepared/stage2/`; committed hash manifests and
compact results document their identities. This storage limitation remains explicit
until remote replication is verified.

## Completion-attempt diagnostics and preservation

The [GPU execution report](../reports/STAGE2_GPU_EXECUTION.md) documents the bounded
layered access check and remaining blocker. Gateway authentication succeeds, but the
upstream pod connection times out; a zero gateway exit status does not prove shell access.
The new offline `scripts/stage2_preflight.py` checks frozen hashes, annotation wording
and public journey consistency. `scripts/preserve_stage2.py` creates a local archive
with per-member checksum verification; it does not claim remote replication. Use the
report's exact commands and inspect any pod-side ledger before resuming the allocation.
