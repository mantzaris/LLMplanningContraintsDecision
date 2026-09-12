# Reproduction and bounded execution

Use Python 3.11 or 3.12. `uv.lock` locks the CPU and optional GPU dependency sets.
The Stage 1 development host used isolated Python 3.11.13 and uv 0.8.17. Its system
`python` was Python 2, so every recorded local command used the project environment.

```bash
uv sync --frozen --extra dev
uv run --frozen plancheck acquire --config configs/data.json
uv run --frozen plancheck prepare --config configs/data.json \
  --feed data/raw/trimet-82e6b822de008367b3d3d35bb52545807ea41b6f56623a9aa4b1162b3d54671b.zip
uv run --frozen --extra dev plancheck cpu-check
```

The acquisition endpoint changes over time. If its new checksum differs from the
frozen configuration, preparation refuses it. Use the retained frozen ZIP or create
an explicitly versioned dataset. `data/prepared/public/` contains only inference
inputs; `data/prepared/private/` contains independent evaluation annotations. The
committed annotation-review CSV is ready for later human checking. It is unaudited.

All methods A–E are implemented in one runner. Config values fix the common pool,
model revision, sampling seeds, candidate count, query/repair/call limits and smoke
subset. Stage 1 rejects held-out IDs and non-model ordinary judgments. The default
smoke config runs four development requests, all five methods, four candidates for
D/E, two judgments, one repair, and at most seven logical calls per method/request.

## GPU environment and execution

First inspect GPU processes, memory, CUDA and storage using `nvidia-smi`, `df`, and
process names only (avoid printing credentials in command arguments). Use an isolated
project directory/venv. The inspected RunPod had a Blackwell RTX PRO 6000, driver
595.91.07, Python 3.12.3 and working PyTorch 2.8.0+cu128. A system-site-packages venv
reused that CUDA runtime; project dependencies were installed only into the venv.
The full installed-version inventory and hardware evidence are retained with the run.
Do not install an older CUDA build without Blackwell support.

The cached model was **Qwen/Qwen2.5-7B-Instruct**, immutable revision
`a09a35458c702b33eeacc393d103063234e8bc28`, Apache-2.0. Its official
[model card](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) documents the model and
license. The [model manifest](../data/manifests/model.json) records official weight
SHA-256 and Git blob identities. All weight shards and tokenizer/config/license
files matched that revision. Existing cache files were read only, never modified.
No new weights, fine-tuning or reinforcement learning were needed.

The final runner also verifies cached files automatically before loading against
the manifest's weight SHA-256 and Git blob identities. The smoke passes performed
the same checks explicitly before execution; the automated helper was added
afterward and tested with identity/corruption fixtures, without another GPU run.

On a suitable GPU machine:

```bash
uv sync --frozen --extra gpu
uv run --frozen plancheck gpu-diagnostic --output runs/gpu-probe.json
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 timeout --signal=TERM --kill-after=10s 3300s \
  uv run --frozen --extra gpu plancheck smoke --config configs/smoke.json \
  --public data/prepared/public --run runs/smoke-v3 \
  --model-path /absolute/path/to/verified/cached/model
```

`model-path` is an environment-specific local cache path; it is not a model identity.
For a fresh environment resolve the exact manifest revision from the official model
repository, verify hashes, and record the download separately from GPU execution.

The RunPod gateway requires `ssh -tt` and ignores remote command arguments. Commands
and payloads must be supplied through shell stdin. [ssh_transfer.py](../scripts/ssh_transfer.py)
provides base64 stdin transfer with a SHA-256 check and an isolated destination root.
It does not use SCP/SFTP/rsync. For an interactive session enter commands after the
shell prompt; never assume a command appended to `ssh` ran. Keep the target and key
path in local shell variables, not repository config or public logs. The provided
named identity was absent on this host; the gateway nonetheless accepted the
existing SSH authentication in PTY mode. No private-key contents were inspected.

## Accounting, artifacts and resume

One aggregate GPU-hour and 100 attempted generations are hard upper limits, not
targets. A locked, append-only `runs/stage1-gpu-budget.jsonl` is shared by sibling
smoke run directories. Time starts immediately before loading the model and ends
after GPU disposal. All inference, warm-up if used, failed calls/retries and idle
time with the model resident are charged. There was no separate warm-up generation.
Each request is reserved before invocation. Unclosed sessions conservatively charge
their entire reserved remainder. A signal deadline and external process watchdog
bound the session. CUDA teardown/watchdog latency can add small conservative
uncertainty; measured runs stop far below the ceiling. Do not reset the ledger to
circumvent limits. Cached calls cost zero actual GPU generation but retain full
logical method costs. Errors with unavailable token counts remain unknown, not zero.

Every run saves a repository revision, code hash (including dirty state), model and
backend revisions, configuration, prompt/data hashes, public inputs, candidates,
plans, witnesses/scores, judgments, repair attempts, structured errors, token counts,
solver/wall timings and GPU evidence. Generation journals are append-only. Outputs
and manifests are immutable. A resume with identical inputs skips completed outputs
and reuses saved successful generations; unsuccessful attempts remain in the journal.
Failed method outputs are retained rather than silently retried. Use a new named
run for a declared revision/correction; the aggregate budget ledger remains shared.

## Offline replay, evaluation and report

These commands require no GPU:

```bash
uv run --frozen python scripts/replay_revision.py --run runs/smoke-v3 --output runs/replay-v3-original
uv run --frozen plancheck evaluate --run runs/smoke-v3 \
  --references data/references/provisional.json
uv run --frozen plancheck report --run runs/smoke-v3 \
  --output artifacts/stage1/smoke-v3-table.md
```

Replay reconstructs the inference boundary from saved public snapshots, reuses exact
prompt/model/seed keyed generations, reruns planning and selection, and compares
decisions/scores/judgments against original outputs (excluding hardware-dependent
timing and cache flags). Missing outputs cause an explicit cache-miss error; no
GPU fallback is possible. Run evaluation separately: no reference path is accepted
by the inference command. Full local run artifacts contain agency schedules and are
not committed under the current redistribution policy. Small public summaries and
content hashes are committed; complete local replay artifacts remain available in
the workspace. See [data.md](data.md) for historical-feed availability limitations.

`replay_revision.py` exports the recorded source revision to a temporary directory,
checks its code hash, and replays with that implementation. It creates no Git branch
or worktree and does not change `main`. Use it for historical runs after parser or
prompt changes. Plain `plancheck replay` uses the currently installed code and is
appropriate when its protocol matches the saved run. Versions v1/v2/v3 remain separate;
v3 used `--cache-from runs/smoke-v2` to reuse model text with the fenced-JSON parser.
One newly required repair generation was charged to the same aggregate GPU ledger.
This format correction did not reinterpret JSON values or change either selector.

`plancheck export-audit --run runs/smoke-v3 --output artifacts/stage1/smoke-v3.json`
exports schedule-free metrics, candidate class counts, selected IDs, scores, verdicts,
errors and full-local-artifact checksums. Fresh invocations inherit the pinned model's
generation configuration: top-k 20 and repetition penalty 1.05; sampled translation
calls override top-p to 0.95 and temperature to 0.7, while judgments/critique/repair
are greedy. Full effective settings and installed packages are in the runtime artifact.

For the isolated gold-label diagnostic ablation:

```bash
uv run --frozen python -m plancheck.diagnostic \
  --fixture tests/fixtures/injected.json --output artifacts/stage1/gold-diagnostic.json
```

This command is explicitly synthetic and diagnostic. It is not an ordinary model
judgment mode and cannot establish the main empirical claim.
