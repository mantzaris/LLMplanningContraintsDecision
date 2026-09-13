"""Regenerate the Stage 3 report from compact, sanitized saved results. CPU only."""

from pathlib import Path
import json
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text())


def main():
    folder = "artifacts/stage3/pilot-v1/"
    result = read(folder + "summary.json")
    rows = read(folder + "rows.json")
    data = read("data/sampling/data-manifest.json")
    protocol = read("data/sampling/protocol.json")
    compute = read(folder + "compute.json")
    storage = read(folder + "storage.json")
    checks = read(folder + "verification.json")
    cfg = read("configs/sampling.json")
    n = result["n"]
    last = max(cfg["checkpoints"])
    summary = result["summary"]
    final = [r for r in rows if r["checkpoint"] == last]
    texts = {s["scenario_id"]: s["request"] for s in read("data/sampling/requests.json")}

    def table(headers, records):
        return "\n".join(
            ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
            + ["| " + " | ".join(map(str, row)) + " |" for row in records]
        )

    def pct(value):
        return f"{100 * value:.1f}%"

    def ratio(k, arm):
        return f"{summary[f'{arm}/{last}'][k]}/{n}"

    metrics = []
    for k in cfg["checkpoints"]:
        for a in "ABC":
            s = summary[f"{a}/{k}"]
            metrics.append(
                [
                    a,
                    k,
                    f"{s['covered']}/{n}",
                    f"{s['correct']}/{n}",
                    f"{s['oracle_correct']}/{n}",
                    s["validation_improved"],
                    s["validation_damaged"],
                    s["judgments"],
                    s["generation_token_exhaustion"],
                    s["validation_token_exhaustion"],
                ]
            )
    paired = []
    for b in "AB":
        for metric in ("covered", "correct"):
            p = result["paired"][f"C-{b}/{last}/{metric}"]
            interval = p["base_bootstrap_95_interval"]
            paired.append(
                [
                    f"C − {b}",
                    metric,
                    f"{p['wins']}/{p['ties']}/{p['losses']}",
                    pct(p["difference"]),
                    f"[{pct(interval[0])}, {pct(interval[1])}]",
                ]
            )
    outcomes = []
    for a in "ABC":
        selected = [r for r in final if r["arm"] == a]
        counts = Counter(r["outcome"] for r in selected)
        outcomes.append(
            [
                a,
                sum(r["reference_feasible"] for r in selected),
                counts["correct_feasible_plan"],
                counts["incorrect_plan"],
                counts["correct_infeasibility"],
                counts["false_infeasibility"],
                counts["unresolved"],
                counts["invalid_model_output"],
                counts["solver_timeout"] + counts["infrastructure_failure"],
            ]
        )
    costs = []
    for a in "ABC":
        s = summary[f"{a}/{last}"]
        research_validation = sum(r["validation_tokens"] for r in rows if r["arm"] == a)
        costs.append(
            [
                a,
                s["logical_calls"],
                s["logical_input_tokens"],
                s["logical_output_tokens"],
                f"{s['mean_generation_tokens']:.1f}",
                f"{s['mean_logical_tokens']:.1f}",
                f"{s['mean_logical_latency_seconds']:.2f}",
                f"{s['solver_seconds']:.3f}",
                s["generation_tokens"] + research_validation,
            ]
        )
    diversity = []
    for a in "ABC":
        s = summary[f"{a}/{last}"]
        diversity.append(
            [
                a,
                s["parsed"],
                s["invalid"],
                s["exact_duplicates"],
                s["behavior_duplicates"],
                f"{s['mean_distinct_signatures']:.2f}",
                f"{s['mean_clause_signatures']:.2f}",
                s["correct_without_equivalent_candidate"],
            ]
        )
    clause_counts = Counter()
    family_counts = Counter()
    for r in data["rows"][:n]:
        family_counts[r["family"]] += 1
        for c in r["clause_coverage"]:
            clause_counts[c["rule"]["requirement"]] += 1
    stage_seconds = compute["stage3_measured_seconds"]
    stage_calls = compute["stage3_calls"]
    recommendation = (
        "The precommitted practical screen was met. A larger independent evaluation may be justified, but no further stage is authorized or running."
        if result["continuation_met"]
        else "Pause expansion of this feedback variant. The precommitted practical screening rule was not met. This pilot does not demonstrate a useful advantage over both simple baselines at the common allowance. Do not launch another inference stage on the strength of executable diversity alone."
    )
    trace = []
    for sid in result["illustrative_ids"]:
        case = [r for r in final if r["scenario_id"] == sid]
        trace.append(
            f"**{sid}.** {texts[sid]}\n\n"
            + table(
                [
                    "Arm",
                    "Signatures",
                    "Candidate coverage",
                    "Ordinary outcome",
                    "Oracle outcome",
                    "Witness judgments",
                    "Final plan",
                ],
                [
                    [
                        r["arm"],
                        r["distinct_signatures"],
                        r["covered"],
                        r["outcome"],
                        r["oracle_outcome"],
                        r["judgments"],
                        r["final_plan_id"] or "—",
                    ]
                    for r in case
                ],
            )
        )
    extra = read(folder + "extra-diagnostics.json")["aggregate"]
    extra_table = table(
        [
            "Arm",
            "Raw coverage, final",
            "After common normalization",
            "New correct behaviors after two",
            "New nonreference behaviors after two",
            "Normalized attempts",
        ],
        [
            [
                a,
                extra[a]["raw_coverage_final"],
                extra[a]["normalized_coverage_final"],
                extra[a]["new_correct_signature_after_shared_two"],
                extra[a]["new_nonreference_signatures_after_shared_two"],
                extra[a]["normalization_affected_attempts"],
            ]
            for a in "ABC"
        ],
    )
    trace_text = "\n\n".join(trace)
    text = f"""# Solver-Guided Semantic Sampling: exploratory Stage 3 pilot

**{n}/{n} fresh base requests completed, one generation trajectory per arm, all three prefixes evaluated.**
Final bounded correct-candidate coverage was A **{ratio("covered", "A")}**, B **{ratio("covered", "B")}**, C **{ratio("covered", "C")}**.
Ordinary final correctness was A **{ratio("correct", "A")}**, B **{ratio("correct", "B")}**, C **{ratio("correct", "C")}**.
**Continuation screen: {"met" if result["continuation_met"] else "not met"}.** {recommendation}

This is a new candidate-generation hypothesis, not a positive continuation of the original weighting claim.
Stage 2's 33/48 D = E and its negative mechanism/annotation findings remain unchanged.
See the preserved [Stage 2 closeout](STAGE2_ANNOTATION_COVERAGE_AUDIT.md).

## Starting state and frozen execution

The clean starting `main` revision was `c094a31177cf17a0529913086d06437f16a3d211`.
Implementation/development rules were pushed in `fd3c74095fe6f2a41bd6218f54669f1c2d3922fa`.
The fresh protocol and analysis were pushed before evaluation in **`{result["run_revision"]}`**.
No historical records, prompts or labels were rewritten. No scoring or sampling change followed fresh outputs.
Source-only literal normalization is common to all arms and cannot be credited uniquely to C.

The [method and overlap review](../docs/stage3-semantic-sampling.md), [configuration](../configs/sampling.json),
[protocol](../data/sampling/protocol.json), [requests](../data/sampling/requests.json),
[references](../data/sampling/references.json), and [review worksheet](../data/sampling/annotation-review.csv)
freeze the experiment. ARTEMIS/SSV establish related validation mechanisms; VERGE and the published
US20250111220A1 application overlap directly with formal/equivalence-guided feedback and resampling.
This is a controlled adaptation/comparative investigation, not a broad novelty claim.

A samples the ordinary prompt independently; B uses fixed source-focused perspectives; C adds bounded deterministic
feedback about earlier full/clause behaviors using the same perspectives. First two calls are exactly shared,
with full logical charges to each arm. Signatures cover every journey in the fixed pool. Equality is bounded
behavioral agreement, not unrestricted semantic equivalence or correspondence with natural language.
Clause signatures retain differences hidden by a rejecting conjunct. Unique source operator/scope associations
and unverified model spans are traceability aids; missing associations are explicitly recorded.
C may repeat the best-supported interpretation. Raw multiplicities are not calibrated confidence.

All trajectories complete before judging. At attempts 2/4/8, all arms use the existing balanced selector D,
identical judge/model/rendering/tie-breaking/stopping rules and at most two judgments, with **no repairs**.
Ordinary generation/selection import no reference or oracle analysis modules. The offline reference checker
remains separate from the prediction compiler. Exact caching requires identical prompt, settings, seed and model.

## Data, inclusion and annotation status

All requests are **constructed over published scheduled services**, not passenger records or observed movements.
The original frozen TriMet feed SHA-256 is `{data["data_config"]["feed_sha256"]}`.
No new source feed was acquired. The public universe uses the existing bbox/route algorithm and service date
{data["data_config"]["service_date"]}, now 10:00–13:00. There are no Stage 1/2 segment OD-pair overlaps, including
reversals; routes, stops, agency and date overlap. Endpoints at 10:00 can touch the prior window. This is fresh
exploratory development material, not an independent publication holdout.

Selected routes: {", ".join(map(str, data["selected_routes"]))}; all bus. Maximum two rides per segment,
120-second connection allowance, deterministic segment cap 128 and joint cap 256. Feasibility and optimality
are conditional on these shared pools. Walking, through-service guarantees, capacity and accessibility are
outside scope; two-segment requests explicitly leave movement between the named segments outside the task.

{table(["Family", "Bases"], sorted(family_counts.items()))}

The set includes {sum(r["feasible_journeys"] > 0 for r in data["rows"][:n])} feasible and {sum(r["feasible_journeys"] == 0 for r in data["rows"][:n])} pool-infeasible requests.
All {sum(clause_counts.values())} reference clauses both accept and reject journeys, and each has a conditional
exclusion with the other clauses held fixed. Each family therefore has effective rather than vacuous coverage.
Modes and ordering were excluded by the coverage rule, not by method outcomes. Adding transport modes would
improve breadth; it would not establish a sampling or selector advantage. Two failed OD coverage checks are
recorded before model evaluation. No assigned cases were excluded or amended.

Separate request-wording grammar checks agree with the references for all requests. References and review
are **provisional developer/automated annotations, not independent human adjudication**. Correlated constructor,
review and evaluator mistakes remain possible. Original review material and blank human-review fields are retained.
CPU regeneration reproduced public inputs and annotation manifests: **{checks["data_reproduced"]}**.

## Budget selection and execution evidence

Historical development used three predeclared requests (`pilot-00`, `17`, `34`),
24 actual translations and {protocol["development"]["measured_gpu_seconds"]:.4f} measured GPU seconds.
No witnesses occurred, so no development judge calls were needed. The predeclared CPU tokenizer fallback
measured 384 possible judge prompts; maximum input was 905 tokens. Maximum translation input was 3,509.
Development p95 inference was {protocol["development"]["p95_call_seconds"]:.4f} seconds; no parameters were swept.
The conservative 32-request forecast was {protocol["forecast_seconds"]["32"]:.2f} seconds, so no reduction to 24 occurred.

Each arm receives **35,000 candidate tokens and 4,000 validation tokens per prefix** (12,000 across all three
prefixes). Before a call, input tokens plus the 768-token output maximum must fit. Successful calls consume
actual input+output; failed unknown outputs would charge the whole reservation. Equal allowances are ceilings,
not assertions of equal consumption. The final-prefix primary comparison uses the same allocated resources;
attempt curves and earlier-prefix evaluation overhead are secondary. Trajectories are not extended just to use
unused tokens or replace malformed/duplicate outputs.

Authenticated access to the supplied project pod succeeded through its authorized direct SSH endpoint with
strict host-key checking and the existing local identity. The init environment confirmed this project's pod;
the historical ledger checksum matched. The separate OverseeingManyLLMs pod was not used.
The isolated directory is `/workspace/LLMplanningConstraintsStage3`. Binary stdin transfers were verified.
One tar ownership-preservation error on the shared volume was resolved using `--no-same-owner` before model
execution; no generations were lost. No pod or billing configuration changed.

The existing pinned Qwen2.5-7B-Instruct revision `a09a35458c702b33eeacc393d103063234e8bc28` ran on
an NVIDIA RTX PRO 6000 Blackwell Server Edition with about 96 GiB memory. Backend: transformers 4.51.3,
torch 2.8.0+cu128, bf16, SDPA, no quantization. Model-file hashes, CUDA parameter placement, generated output
device and GPU process/memory probes were saved. Sampling used temperature 0.7/top-p 0.95, with cached model
defaults top-k 20/repetition penalty 1.05; ordinary judging used temperature zero and fresh contexts.
Translation and judgment use the same model, which is not an independent truth oracle.
All project inference processes exited; post-exit GPU check: **{checks["gpu_idle_after_exit"]}**.

## Outcomes under common allowances

Coverage below means any candidate matching reference acceptance over the finite pool. A correct returned
plan does not establish a faithful formalization. “Validation improved/damaged” compares the final
output with the initial selected candidate in that same prefix; no repairs were performed. The oracle column uses separate CPU reference labels and no
model repairs; it is privileged diagnostic evidence. Every assigned base stays in the denominator.

{table(["Arm", "Attempts", "Covered", "Ordinary correct", "Oracle correct", "Validation improved", "Damaged", "Judgments", "Gen. exhausted", "Val. exhausted"], metrics)}

Final-prefix outcome categories:

{table(["Arm", "Feasible bases", "Correct plan", "Incorrect plan", "Correct infeas.", "False infeas.", "Unresolved", "Invalid model", "Timeout / infra"], outcomes)}

Final paired comparisons (wins/ties/losses refer to C against the baseline):

{table(["Comparison", "Metric", "W/T/L", "Difference", "Base bootstrap 95% interval"], paired)}

These exploratory intervals resample entire base requests (10,000 fixed-seed draws). Prefixes, samples and
witnesses are not independent observations. A degenerate bootstrap interval when outcomes coincide is not
proof of population equivalence. One model, one replicate and correlated templated requests limit inference.
No significance or publication-scale claim follows from this screen. In infeasible pools, any all-rejecting formula can match the full reference signature; the clause diagnostics expose variation but do not establish source-semantic correctness. No independent source-semantic adjudication was performed.

## Mechanism and inference cost

{table(["Arm", "Parsed attempts", "Invalid", "Exact duplicates", "Behavior duplicates", "Mean full signatures", "Mean clause signatures", "Correct without full equivalence"], diversity)}

The clause count groups by source association and acceptance signature; absent associations are marked in
per-request rows. Different signatures may be wrong. The raw and normalized formulas and every feedback prompt
remain in preserved artifacts. `discovery.json` records first correct-candidate discovery against accumulated
candidate tokens, so a normalization or duplication effect can be inspected without attributing it to C.

{table(["Arm", "Logical calls, final", "Input tokens", "Output tokens", "Mean gen. tokens", "Mean total tokens", "Mean inference sec.", "Solver sec.", "Study tokens incl. earlier validation"], costs)}

Final logical charges include the candidate prefix and its validation calls independently for each arm,
including shared cache hits. The last column counts full generation once plus all prefix validation allocations
actually consumed. It does not count the same generation again at prefixes 2 and 4. Logical inference latency is
summed from saved calls, including cached attribution; actual model-resident wall time includes additional loading
and between-call work. Solver time is CPU time and separately attributed. Fewer calls do not imply equal tokens.

Actual fresh compute: **{result["actual_fresh_calls"]} requests**, {result["actual_fresh_failed_calls"]} failed calls,
{result["actual_fresh_input_tokens"]:,} input and {result["actual_fresh_output_tokens"]:,} output tokens;
{result["actual_fresh_inference_seconds"]:.2f} summed generation seconds.
Distinct ordinary judgments: {result["distinct_judgments"]}; incorrect versus provisional references:
{result["wrong_distinct_judgments"]}; uncertain: {result["uncertain_distinct_judgments"]}.
The per-judgment [checks](../{folder}judge-checks.json) are offline only.
Oracle correctness at the final allowance: A {ratio("oracle_correct", "A")}, B {ratio("oracle_correct", "B")}, C {ratio("oracle_correct", "C")}.
No oracle labels were fed into candidate generation or ordinary selection.

## What failed and what the feedback changed

All seven C failures (`01,04,12,17,20,25,28`, with prefix `sampling-`) are latest-departure
requests. Their wording explicitly says “depart no later than”; the reference uses an inclusive upper bound.
C retains lower-bound interpretations (`depart_ge`), sometimes with additional invented requirements or wrong
numeric values. These are observable source/operator errors, not unresolved wording or a timezone convention.
The common normalizer deliberately does not turn an incorrect operator into a correct one. It fixes only a
uniquely bound existing time value. Seven of eight latest-departure requests therefore remain wrong in C;
the timing, transfer, segment-scope and infeasible families all resolve correctly.

The following **secondary offline diagnostic** compares saved raw formulas with the common normalized formulas.
It uses reference labels only for analysis and was not used to select prompts, cases or candidates.

{extra_table}

C receives canonical numeric values in the feedback about its normalized prior candidates. Its higher raw-formula
coverage is consequently not an advantage at the common normalized interface. C adds **zero** new correct full
behaviors after the shared two samples, versus two for A and six for B; it adds only one nonreference behavior.
The observed feedback trajectory mostly preserves earlier behaviors, including incorrect inequality directions.
This supports a narrow failure diagnosis consistent with anchoring on earlier formulas; the experiment does not
identify the model's internal reasoning or prove all feedback mechanisms behave this way. Increasing diversity
was not itself the objective, and the newly observed wrong alternatives in A/B do not count as useful coverage.

Eleven of 19 distinct ordinary judgments are wrong under the provisional reference labels. Incorrect judgments
often assert the correct date/stops while failing to check the departure bound; syntactically valid source spans
(e.g. the beginning of the date) are not evidence of relevant semantic checking. At the final prefix, B has a
reference-equivalent candidate in `12,25,28`, but ordinary judgments discard it; the oracle resolves all three.
B's remaining failure `20` lacks that candidate. These are judge and candidate-coverage bottlenecks, respectively.
C's oracle remains 25/32 because correcting witness labels does not supply the missing upper-bound candidates.

Oracle output correctness is not an upper bound when the correct candidate is absent. The only ordinary correct
plan without full candidate equivalence occurs in A on `sampling-20`: the requested departure is at most
10:55:00, while a sampled lower bound requires at least 10:55:00. The solver's selected plan departs exactly at
that shared boundary and happens to satisfy the request. Two erroneous positive witness judgments retain this
candidate; truthful oracle judgments remove it and the oracle returns an incorrect plan. This explains A's
28 ordinary versus 27 oracle correct results. The diagnostic is reported because it is the complete set of such
weak-success cases, not as a favorable representative example or a benefit of inaccurate judging.

The main final comparison is worse for C by 9.375 percentage points in ordinary correctness against each
baseline, with zero wins and three losses. Coverage is lower by 6.25 points versus A and 18.75 points versus B.
C consumes about 31% more final logical tokens than A and 30% more than B. It meets neither practical threshold.
This is negative evidence for the tested variant under these conditions; the small sample still limits broader claims.

## Illustrative saved cases and figures

The frozen rule selects first-ID C-only coverage gain, first C failure, first three-arm tie, removes duplicates,
and falls back to the first assigned ID if needed. These examples are illustrative, not representative sampling.
In `sampling-01`, the request's 10:54:48 upper bound is 39,288 service-day seconds.
A and B eventually sample `depart_le(39288)`; C retains `depart_ge(39448)` throughout.
The balanced witness `00b783dfaa8092dc3eae` separates these readings, and its ordinary satisfied judgment
correctly selects the upper-bound plan for A/B. C has no witness and keeps an incorrect plan. The oracle agrees
with these outcomes. In the tie case `sampling-00`, every arm already covers the reference and validation adds
no necessary recovery. Full formulas and acceptance vectors appear in [heatmaps.json](../{folder}heatmaps.json); raw prompts, outputs,
selected witnesses and updates remain in the archived run.

{trace_text}

Four figure sets are generated entirely from actual saved artifacts, each with PDF, SVG and PNG:

- [Coverage versus consumed candidate tokens](../{folder}figures/coverage.pdf).
- [Final correctness versus consumed total tokens](../{folder}figures/correctness.pdf).
- [Candidate-by-journey behavior heatmaps](../{folder}figures/behavior-heatmaps.pdf).
- [Operational failure decomposition](../{folder}figures/failure-decomposition.pdf).

Curve points are observed prefix means (attempt labels 2/4/8), not interpolated equal-token successes. The shared
final allowance is the primary comparison. White/blue heatmap cells mean reject/accept; gray means invalid.
The failure plot distinguishes absent reference-equivalent candidates from selection failure with such a
candidate available. This diagnostic distinction does not assume full equivalence is necessary for every
correct final plan; those weaker successes are counted separately.

## Accounting, artifacts and reproduction

| Allocation | Actual requests | Measured GPU seconds | Conservative extra allowance |
| --- | --- | --- | --- |
| Historical cumulative | 404 | 919.0111 | ≤60 s |
| Stage 3 development + fresh | {stage_calls} | {stage_seconds:.4f} | ≤{compute["stage3_uncertainty_seconds"]} s |
| New cumulative | {404 + stage_calls} | {919.0111 + stage_seconds:.4f} | ≤{60 + compute["stage3_uncertainty_seconds"]} s |

The Stage 3 ledger is separate and append-only: measured guard 7,080 seconds, maximum four sessions,
1,500 actual requests; 30 seconds per session reserved for conservative teardown uncertainty. The actual total
including margins remains below 7,200 seconds. CPU file checks, replay and analysis do not use GPU inference.
Historical ledgers are byte-for-byte preserved: **{checks["historical_ledgers_unchanged"]}**.

Raw artifacts are copied locally and replicated on the existing pod's persistent project volume. This is
verified replication, not a guarantee against loss of the rented storage. The archives preserve unsuccessful
setup records, raw generations, exact-cache calls, normalized interpretations, pools, all prefix outputs,
oracle diagnostics and GPU evidence; model weights and credentials are excluded. Compact artifacts in Git
include metrics, manifests, figures, checksums and illustrative signatures; large raw schedules remain outside Git.

{table(["Archive", "SHA-256", "Verified storage"], [[r["name"], r["sha256"], r["remote_path"]] for r in storage["archives"]])}

The [storage manifest](../{folder}storage.json) and [input checksums](../{folder}input-checksums.json)
record exact files. Focused tests and full existing suite: **{checks["tests_passed"]} passed**.
All three development and all {checks["fresh_replay_matches"]} fresh base outputs replayed exactly
(including candidates, witnesses, updates, costs and outputs; only cache-location flags differ).
Model generations were not repeated for replay. CPU analysis and figure generation use the saved records. Replay preserves saved solver records and timings while regenerating normalized behaviors, prompts, judgments and selection from cached model responses.

From the repository root with the locked Python environment:

```bash
# Acquire the preserved archive using the locally configured authenticated connection;
# verify its SHA-256 before extracting it into the repository's ignored runs/ directory.
uv sync --frozen --extra dev --extra analysis
.venv/bin/python -m plancheck.sampling_run --config configs/sampling.json \\
  --public data/prepared/stage3/public --run runs/stage3-replay-new \\
  --replay-from runs/stage3-fresh
MPLCONFIGDIR=/tmp/plancheck-mpl .venv/bin/python -m plancheck.sampling_analysis \\
  --run runs/stage3-fresh --references data/sampling/references.json \\
  --output runs/stage3-analysis-reproduced
.venv/bin/python scripts/stage3_extra_diagnostics.py \\
  --run runs/stage3-fresh --references data/sampling/references.json \\
  --output runs/stage3-extra-diagnostics-reproduced.json
# Compact-artifact figures and report need no raw model outputs or GPU:
MPLCONFIGDIR=/tmp/plancheck-mpl .venv/bin/python -m plancheck.sampling_analysis \\
  --output artifacts/stage3/pilot-v1 --figures-only
.venv/bin/python scripts/stage3_report.py
```

If public inputs are absent, copy saved `public-scenarios.json` to a new public `scenarios.json` and the saved
`pools/` directory alongside it, or regenerate with `sampling_data` using the frozen feed. Exact replay uses
execution revision `{result["run_revision"]}` or matching package source hash; later documentation/results
commits do not change that hash. Development replay requires its recorded implementation source revision.

## Disposition

{recommendation}

The reusable result is an executable, auditable candidate-sampling comparison with common normalization,
exact bounded full/clause signatures, token admission and offline replay. It is not evidence that the original
consequence-weighting claim succeeded. Generic validation and deterministic normalization retain engineering
value, but neither should be renamed a novel contribution. This small, provisional, bus-only constructed set
cannot establish unrestricted semantic correctness or broad model/network generalization. No larger study,
additional candidate mechanism, fine-tuning or inference beyond this authorized pilot was launched.
"""
    (ROOT / "reports/STAGE3_SEMANTIC_SAMPLING_PILOT.md").write_text(text)


if __name__ == "__main__":
    main()
