# Reproducing and resuming Stage 2

Use Python 3.11 or 3.12 and the committed `uv.lock`. The local verified environment
uses Python 3.11.13; the earlier GPU environment used Python 3.12.3. Run these commands
from the repository root. The fresh pilot is complete: 48 bases, one replicate under the frozen timing rule.
The GPU execution report separates it from historical CPU reanalysis. Reproduction
requires no further GPU inference; do not relaunch the completed allocation.

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

## Recorded GPU execution and transport

The user-provided direct SSH connection resolved the gateway routing failure. Its
provider pod ID and historical ledger were checked before execution. The separate
pod used by the related `OverseeingManyLLMs` repository is not this project's pod.
Keep the supplied host/port and credentials in local settings; do not infer an endpoint
from another project. Use finite timeouts and strict known-host verification. The
verified environment is `/workspace/LLMplanningConstraintsStage1/.venv`, model cache
`/workspace/AgentRobustComms/stage2/model`, and new Stage 2 clone
`/workspace/LLMplanningConstraintsStage2/project`. The existing environment is reused
with `PYTHONPATH`; other projects' environments and workloads are not modified.

The following commands document the setup/launch already completed at `a544f318`.
They are not instructions to rerun GPU inference on the completed sample. A future
resume must preserve the existing clone, run identity and cumulative stage ledger.

Code and public-data archives were transferred with verified SSH command execution
and binary stdin. This works without SCP/SFTP. With `RUNPOD_TARGET` and `RUNPOD_PORT`
set privately to this project's authorized direct connection, the equivalent transfer
pattern is below. `test ! -e` prevents replacing an existing artifact; compare the
printed local and remote hashes before extraction. No credentials enter the archive.

```bash
git bundle create /tmp/plancheck-stage2.bundle main
tar -czf /tmp/plancheck-stage2-public.tar.gz -C data/prepared/stage2 public
ssh -i ~/.ssh/id_rsa -p "$RUNPOD_PORT" -o BatchMode=yes \
  -o ConnectTimeout=15 -o StrictHostKeyChecking=yes "$RUNPOD_TARGET" \
  'test ! -e /workspace/LLMplanningConstraintsStage2/project.bundle && cat > /workspace/LLMplanningConstraintsStage2/project.bundle' \
  < /tmp/plancheck-stage2.bundle
sha256sum /tmp/plancheck-stage2.bundle
ssh -i ~/.ssh/id_rsa -p "$RUNPOD_PORT" -o BatchMode=yes \
  -o ConnectTimeout=15 -o StrictHostKeyChecking=yes "$RUNPOD_TARGET" \
  'sha256sum /workspace/LLMplanningConstraintsStage2/project.bundle'
```

Use the same pattern for `public.tar.gz`. The historical gateway's PTY/base64 helper
`scripts/ssh_transfer.py` is retained, but was unnecessary on the working direct route.
The public archive contains no reference constraints. The Git bundle includes committed
annotations, which ordinary inference does not read.

The original launch used a fresh isolated Stage 2 directory.
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

The completed fresh run is replicated on persistent pod storage and locally; see the
GPU execution report and compact verification records for exact paths/checksums.
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

## Compact export, diagnostic audit and accounting

The ordinary runtime has finished. These commands inspect saved outputs only:

```bash
uv run --frozen python scripts/stage2_fresh_diagnostics.py \
  --run runs/stage2-pilot-v1 --analysis runs/stage2-pilot-analysis-v1 \
  --public data/prepared/stage2/public --references data/pilot/references.json \
  --output runs/stage2-pilot-diagnostics-v1
uv run --frozen python scripts/stage2_execution_accounting.py \
  --run runs/stage2-pilot-v1 --ledger runs/stage2-gpu-budget.jsonl \
  --previous artifacts/stage2/gpu-accounting.json \
  --output artifacts/stage2/pilot-v1/gpu-accounting.json
uv run --frozen python scripts/export_stage2.py --run runs/stage2-pilot-v1 \
  --analysis runs/stage2-pilot-analysis-v1 --output artifacts/stage2/pilot-v1 \
  --replication-record artifacts/stage2/pilot-v1/replication.json
```

A replication record is evidence from a completed checksum-verified transfer; do not
supply one speculatively. The exporter otherwise records unverified storage. The
supplementary diagnostic files can be copied from `runs/stage2-pilot-diagnostics-v1`
to the compact result directory after checking immutable identities. They contain
no full schedules/prompts. The accounting command reads the historical pre-execution
snapshot and full current Stage 2 ledger, avoiding double-counting that allocation.

Plots can be regenerated using just committed compact summaries:

```bash
uv run --frozen --extra analysis plancheck pilot-figures \
  --analysis artifacts/stage2/pilot-v1 --output /tmp/stage2-pilot-figures \
  --label 'Fresh development pilot: 48 bases, 1 replicate; provisional references'
```

## Restore retained raw inputs without replacing records

`/workspace/LLMplanningConstraintsStage2/stage2-pilot-v1-results.tar.gz` contains the
fresh run, ledger and launch diagnostics. The earlier 154-file archive under its
`preservation/` directory contains frozen prepared inputs and historical CPU records.
Offline oracle/analysis/replay records have another archive documented by
`artifacts/stage2/pilot-v1/offline-replication.json`. All transfers were checksum-verified.
They are on the authorized persistent volume; this is not an independent provider backup.

Download with a verified direct SSH `cat` into a new local file, then compare SHA-256
against the committed replication record. For example, with private connection variables:

```bash
ssh -i ~/.ssh/id_rsa -p "$RUNPOD_PORT" -o BatchMode=yes \
  -o ConnectTimeout=15 -o StrictHostKeyChecking=yes "$RUNPOD_TARGET" \
  'cat /workspace/LLMplanningConstraintsStage2/stage2-pilot-v1-results.tar.gz' \
  > /tmp/stage2-pilot-v1-results.tar.gz
sha256sum /tmp/stage2-pilot-v1-results.tar.gz
```

Its expected hash is `1f8b63fb3e863ec9564910bfdaf8e7304b878089cb2ff7da54d964a966383871`.
After verifying both archives, extract into **new** directories for inspection. Do not
overwrite a local allocation journal with an older archive. In a separate restored
analysis area, pass the restored `runs/stage2-pilot-v1` as `--run` and the historical
archive's `data/prepared/stage2/public` as `--public` to the CPU commands above; keep
reference inputs pointed at the committed `data/pilot/references.json`. Run
`replay_revision.py` from this Git repository so it can export the recorded source.
Use new output paths if analysis code changes; original results remain immutable.

The [fresh GPU execution report](../reports/STAGE2_GPU_EXECUTION.md) provides final
usage, limitations and the bounded follow-up recommendation. The earlier gateway
blocker and preflight remain in the [archived access report](../reports/STAGE2_GPU_ACCESS_ATTEMPT_20260912.md).
No configuration refreeze, second replicate or further GPU stage was authorized by
completion of this run.
