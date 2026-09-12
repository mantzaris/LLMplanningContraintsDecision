# Pending Stage 2 GPU execution: access diagnosis and preservation

**The fresh GPU pilot did not run. Zero of 96 scenario/replicate pairs completed.**
The current connection failure is verified beyond the earlier timeout reports: local
DNS, gateway TCP, host-key verification and RSA public-key authentication all succeed;
the gateway then times out on its connection to the pod. No current pod shell or
configured alternate authenticated route was available. This is not a fresh negative
selector result. Candidate diversity, D/E divergence, outcome differences and the
fresh oracle comparison remain unmeasured.

The single action needed from the user is to **provide a current working connection
from the RunPod Connect panel for this same existing pod**. An authenticated Jupyter
connection may suffice if the pod's SSH service is unavailable. No pod creation,
replacement, restart, billing change or broader experiment is requested or performed.

## Actual starting state and protocol preservation

This completion attempt began at **`0e31373734c8b2077b6194fc65cf294b1f42cbf3`** on a
clean `main`. Remote `origin/main` matched that commit. No applicable `AGENTS.md` was
found at the repository or its ancestors. The [historical CPU-only report](STAGE2_CONTROLLED_PILOT.md),
[execution instructions](../docs/stage2-running.md), frozen configuration, protocol,
prepared data, provenance manifests and local budget journals were inspected.
There was no fresh pilot manifest or completed pair in the local workspace or remote
Git records. Pod-side storage could not be inspected, so completion elsewhere on that
unreachable pod cannot be independently ruled out; its ledgers must be checked before
any future launch.

The original protocol commit is `1aa2ad1d5291d21be9ee99150e2baf51e9a62d96`;
the historical replay adapter fix is `df7c5b2a986d798c1b261888e6100b66f6423fe7`.
The frozen 48 base requests, two replicates, budgets 0/1/2/4, four candidates, prompts,
sampling settings, solver objective, common journey pools, selectors and elimination-only
D/E update policy are unchanged. No correctness fix or protocol amendment was needed.
The implementation changes in this attempt are two offline utilities for checking the
existing inputs and packaging retained records. Neither is imported by ordinary inference.
There is **no GPU execution revision**, because loading and generation never started.

## Bounded connectivity diagnosis

Troubleshooting ran from **17:55:44 to 18:01:35 UTC on 2026-09-12**, about six minutes,
within the approximately 20-minute limit. One new authenticated SSH probe was used,
with a 15-second connection timeout, one connection attempt, a 180-second outer wall
limit, strict host-key checking, and the existing normal RSA identity. It completed
in **136.338 seconds**. A separate read-only TCP banner check identified the gateway
before the authenticated probe. Repeating the same failed route was unnecessary.

| Layer | Measured result | Implication |
|---|---|---|
| Local DNS | Gateway hostname resolved | No observed DNS failure |
| Gateway TCP | Connection succeeded; SSH banner received | Gateway is reachable from this host |
| Host identity | Existing known-host key verified | No verification bypass or blind known-host replacement |
| Client identity | Existing RSA public key offered and authenticated | Missing `id_ed25519` is not the blocker |
| Gateway routing | Gateway reported an upstream connection timeout | Failure occurs after successful gateway authentication |
| Pod shell/service | Shell sentinel never executed | Pod SSH availability/state cannot be inspected |

The gateway exited with code zero despite reporting the upstream timeout. Exit status
alone would therefore incorrectly suggest success; the probe checked authentication,
the upstream diagnostic and actual shell output separately. Full verbose logs remain
private outside the repository and the preservation archive. The committed
[sanitized diagnostic](../artifacts/stage2/execution-attempt-20260912/connectivity.json)
contains no private key, token, authenticated URL, pod target string or internal address.

Alternative-route inspection covered the normal SSH configuration, existing local SSH
configuration files used by the related research workspace, relevant project connection
files, Jupyter runtime configuration, editor Jupyter/remote configuration and RunPod CLI
configuration. Other recorded endpoints could not be associated with this pod and were
not contacted. Thirty local notebook-server configuration records contained no RunPod
connection; the relevant editor records also contained none. The local RunPod CLI
configuration exists but its API key is empty, and no RunPod credential was configured
in the environment. Consequently authenticated pod lookup was unavailable; the documented
[RunPod pod lookup API](https://docs.runpod.io/api-reference/pods/GET/pods/podId) requires
an authorization credential. No authenticated Jupyter endpoint for this pod was found,
so none was invented or probed by guessing ports.

No current GPU identity, memory, model cache, running workload or pod-side service was
verified in this attempt. The earlier verified Qwen2.5-7B/Transformers/CUDA environment
remains historical evidence only. No pod, process, service, host-key record or billing
setting was modified. Connection attempts stopped once all discovered authorized routes
were accounted for. A request for the current same-pod connection was sent while local
preservation work continued.

## Pre-evaluation annotation and universe checks

The [preflight record](../artifacts/stage2/execution-attempt-20260912/preflight.json)
confirms exact agreement with the frozen hashes for configuration, prompts, public
scenarios, references, data manifest and retained TriMet ZIP. The selected scenario
order and 48 unique base IDs are intact. No injected candidate error was introduced.
The original annotation-review CSV is unchanged; its checksum is included in preflight.

The existing independent narrow wording parser again matched **48/48 requests** to
reference dictionaries. The independent evaluator finds **40 feasible and eight
infeasible requests** in their declared pools. The additional offline checks covered
all **4,366 journey memberships in 48 pools**: text/public endpoint and date agreement,
segment scope/order, stop/trip identities, route/mode membership, ride-count bounds,
chronological scheduled calls, connection stops and minimum timing, journey horizon,
and exclusion of the previously selected OD pairs. No discrepancy or ambiguous
unhandled requirement was identified by these checks. No cases were corrected, dropped
or silently rewritten; amendment and annotation-issue lists are empty.

This remains automated consistency checking of assistant-authored requests and reference
annotations, **not human audit or proof of intended semantics**. The provisional label
is retained. Human review was not treated as a condition preventing this exploratory
pilot; connectivity alone prevented GPU execution. Reference files were used only by
the offline preflight, never supplied to a translator, selector or ordinary judge.
The previously documented bus-only network, limited transfer behavior and conditional
pool completeness remain unchanged.

## Fresh experiment and oracle status

| Required fresh measurement | This attempt |
|---|---|
| Base requests executed | 0 of 48 |
| Scenario/replicate pairs completed | 0 of 96 |
| Integration generations / new timing batch | 0 / not run |
| Parsed interpretations and exact duplicates | Not measured |
| Semantic alternatives / distinguishing witnesses | Not measured |
| Reference-equivalent candidate coverage | Not measured |
| Correct selected plans without equivalent formulas | Not measured |
| Consequence variation / D–E example divergence | Not measured |
| D–E final-output differences or correctness effect | Not measured |
| Model-judgment errors, uncertain outputs or repair damage | Not measured |
| Fresh oracle replay | No candidate bundles to replay |

All 96 planned pairs remain explicitly pending in the
[execution-status artifact](../artifacts/stage2/execution-attempt-20260912/execution-status.json).
No replicates or bases were reduced: the included candidate-only throughput diagnostic
could not begin, so the predeclared reduction rule was not invoked. There is no fresh
correct-resolution estimate, wins/ties/losses count, coverage estimate or confidence
interval at any judgment budget. These quantities are recorded as unknown rather than
zero measured performance. No conditional divergence subgroup exists to analyze.

No existing figure was relabeled or regenerated as fresh evidence. The historical
CPU-only report and its figures remain intact. The four previously completed historical
pairs were replayed with their recorded source revision as an integrity check; **4/4
paired artifacts matched exactly**, with zero model calls. The [verification](../artifacts/stage2/execution-attempt-20260912/replay-verification.json)
explicitly identifies those as historical records. Their old performance is not used
as an answer to the fresh pilot's research questions. All **32 existing tests pass**,
and both new offline utilities pass Ruff checks and were exercised on the actual files.

## Compute accounting

The local Stage 2 ledger contains only its original allocation event, and its checksum
is unchanged. No model-resident session or generation request was started. The original
Stage 1 ledger is also unchanged.

| Accounting scope | Generation attempts | Model-resident GPU seconds | Conservative additional uncertainty |
|---|---:|---:|---:|
| This completion attempt | 0 | 0 | 0 |
| Stage 2 total | 0 | 0 | 0 |
| Historical Stage 1 | 46 | 237.390215 | ≤30 seconds |
| Cumulative | 46 | 237.390215 | ≤30 seconds |

The existing total Stage 2 ceilings remain **1,500 generation attempts and 7,200 aggregate
GPU seconds**. The frozen programmatic guard is 7,170 seconds, leaving the already
specified 30-second disposal/watchdog margin. This attempt creates no new allowance.
There were zero input/output inference tokens, loading, warm-up, retry, repair or GPU
latency costs. Connection diagnosis is not GPU use. Local annotation evaluation, tests,
archive creation and historical replay are CPU work, not CPU model inference. No
project-owned inference process was launched and no rented pod was terminated.

## Artifact preservation and actual storage

The inventory includes the prepared fresh public pools and private provisional
annotations; both historical reanalysis versions and their analyses; the failed v1
replay; the successful v2 replay; this attempt's preflight and historical integrity
replay; and both cumulative GPU journals. Original records were preserved in place.
The raw GTFS ZIP and model caches/weights were not duplicated into the archive.

A local archive was created and **every archived member was read back and verified**
against its source SHA-256 and byte count:

- Location: `runs/stage2-preservation-20260912-execution/stage2-retained-artifacts.tar.gz`
- Verified members: **154**; total uncompressed bytes: **21,305,080**.
- Archive bytes: **693,342**.
- Archive SHA-256: `f5cfac0529e88e971b1a384bf3383ed6113b43d2de25f0592c59f3459e2fc62a`.
- Canonical source-manifest SHA-256: `dc97265fa80fb7a1fb90bb7f9e9babc365996fd156b51c06123e547880cd4e9d`.

See the committed [per-file inventory](../artifacts/stage2/execution-attempt-20260912/source-manifest.json)
and [archive verification](../artifacts/stage2/execution-attempt-20260912/archive-verification.json).
The archive stays outside ordinary Git because it contains derived agency schedules.
Compact, sanitized records and checksums are committed and pushed. **Remote or independent
durable replication of the archive has not succeeded.** A second local copy is not a
claim of durable replication. Its intended established remote project location is
`/workspace/LLMplanningConstraintsStage2/preservation`; the unreachable pod prevented
transfer and remote checksum verification. Previously stored remote Stage 1 artifacts
were not changed.

## Reproduction and continuation

Run from the repository root using the existing Python 3.11/3.12 environment:

```bash
uv sync --frozen --extra dev --extra analysis
uv run --frozen python scripts/stage2_preflight.py \
  --feed data/raw/trimet-82e6b822de008367b3d3d35bb52545807ea41b6f56623a9aa4b1162b3d54671b.zip \
  --output runs/stage2-execution-preflight
uv run --frozen python scripts/replay_revision.py --run runs/stage2-history-v2 \
  --output runs/stage2-execution-historical-replay
uv run --frozen --extra dev plancheck cpu-check
uv run --frozen python scripts/preserve_stage2.py \
  --output runs/stage2-preservation-20260912-execution
```

The utilities refuse to overwrite conflicting immutable artifacts. Use a new preflight
or preservation identity if source records change; the recorded revision and inventory
are historical state, not fields to rewrite. Exact archive byte hashes include source
file metadata, so a fresh archive may have a different compressed hash while all member
content hashes still agree.

After a working connection to the same pod is supplied, first inspect existing pod-side
runs and both journals. Reconcile any successful work found there before launching or
copying a local zero-use ledger; **never overwrite a remotely spent allocation**. Inspect
GPU/workloads and the verified model environment. Then use the already documented
[stdin transfer and frozen pilot commands](../docs/stage2-running.md), keeping the
existing aggregate ledger and resume checkpoints. A verified remote shell and actual
GPU generation evidence are prerequisites; exit code zero from the gateway is insufficient.

The retained archive can be transferred with the existing helper after authentication
works, using the target stored privately in `RUNPOD_TARGET`:

```bash
python3 scripts/ssh_transfer.py --identity ~/.ssh/id_rsa --target "$RUNPOD_TARGET" \
  --local runs/stage2-preservation-20260912-execution/stage2-retained-artifacts.tar.gz \
  --remote-root /workspace/LLMplanningConstraintsStage2/preservation \
  --remote-name stage2-retained-artifacts-20260912.tar.gz
```

Require the helper's remote checksum success before updating replication status. Do
not extract over historical files. No SCP/SFTP/rsync or guessed direct endpoint is needed.
The existing pilot-run, pilot-analyze (separate oracle), replay and plotting commands
remain unchanged. No extra diagnostic generations or alternative candidate prompts are
authorized by this failed connection attempt.

## Recommendation

**Remain inconclusive because access prevents the frozen experiment.** The current
CPU checks support input and replay integrity; they do not demonstrate fresh GPU
operation, useful candidate alternatives, different selector choices, improved outcomes
or value after inference cost. There is no basis here to revise the score, select
favorable cases, expand compute, or claim an improvement.

The next action is restoring a usable connection to this same pod, then completing
the existing predeclared sample within its remaining total allocation. The candidate
bottleneck cannot be re-diagnosed without fresh bundles. If it persists after completion,
a later separately frozen candidate-generation comparison could test four explicitly
source-grounded alternative parses against the current four independently sampled
parses at matched generation cost. That experiment is only a conditional future
proposal; it was not implemented or evaluated in this frozen pilot.
