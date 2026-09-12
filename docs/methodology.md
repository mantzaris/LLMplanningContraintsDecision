# Stage 1 methodology, frozen policy v1

Working title: **Validating LLM Planning Constraints Through Decision-Relevant Examples**.
Civilian scheduled public-transport planning is the application. Timing, exclusion,
resource and dependency interpretation motivate broader decision support; this work
does not provide military operational validation.

An LLM can produce the wrong formal constraints while a solver correctly solves
them. We investigate whether a limited semantic-validation budget is better spent
on examples that separate interpretations with different consequences for selected
plans. Solver correctness does not establish correspondence with natural language.

## Declared universe and language

Public scenario metadata and a frozen feed define a deterministic journey pool
`Pi_D`, shared by every method. Neither reference annotations nor generated formulas
enter pool construction. The planner chooses earliest final scheduled arrival,
then fewest boardings, earliest initial departure, and lexicographic journey ID.
All feasibility, equivalence and optimality claims are conditional on this pool.

The JSON AST supports conjunction, Boolean negation, inclusive arrival/departure
bounds in integer service-day seconds, maximum transfer counts, permitted/excluded
modes, and ordered stop calls. Atoms have a named public segment scope or `all`.
`all` time bounds concern the first departure/final arrival. `all` transfer counts
sum segment transfers. A transfer is an additional boarding within a segment;
turnaround is not a transfer. Stop and trip IDs remain GTFS identifiers. A visit
is a scheduled call, including while remaining on board; it promises no activity
or dwell duration. Adjacent repeated call IDs at transfers collapse for visit order.
Source spans are optional zero-based, half-open character offsets. They provide
traceability, not a correctness certificate.

Conditions, fares, capacity, accessibility, walking, minimum dwell, and open-ended
temporal logic are unsupported. A request requiring these must produce a structured
unsupported outcome. Malformed syntax/units/spans and unknown entities have distinct
outcomes. Z3 selects a finite pool index; binary SAT/UNSAT rank search proves the
deterministic optimum within that pool. Unknown or an expired solver deadline
returns timeout, never infeasible. A separate reference schema and evaluator use
independent traversal, arithmetic and visit checking.

## Consequence policy (freeze before model outputs)

Generate four interpretations in the smoke test (configurable), with distinct
sampling seeds. Deduplicate structural identity without source pointers, then
deduplicate full truth vectors over `Pi_D`. Preserve alias counts for audit; every
semantic class has one vote. No hidden-label choice chooses the representative.

For candidates `C_i,C_j`, exact evaluation computes
`W_ij = {p in Pi_D : C_i(p) != C_j(p)}`. Their respective selected plans are
`pi_i,pi_j`. Define

`I_ij = 1[C_j(pi_i)=false] + 1[C_i(pi_j)=false]`.

A term with no selected plan contributes zero and the missing-plan outcome remains
recorded. Thus a satisfiable/unsatisfiable pair gets one cross-violation term from
the existing plan; two unsatisfiable candidates are pool-equivalent. A timed-out
candidate retains its exact truth vector, but its missing plan supplies no impact
term. This convention underweights unknown consequences and is not evidence of
agreement. The score identifies consequential disagreement, not who is right.

Choose an unused journey maximizing
`sum_{i<j} (1+I_ij) * 1[p in W_ij] / cost(p)` over surviving candidates.
Cost is **one model invocation** in frozen v1. This normalizes to a request budget,
not a token budget; prompt lengths and measured tokens are reported separately.
Positive prospective token costs are supported, but not used/tuned in Stage 1.
Ties use lexicographic journey ID with exact rational arithmetic.

The balanced comparison replaces every pair weight by one. With equal costs its
score is `n_accept * n_reject`, maximizing a balanced partition. All candidates,
journeys, witness generation, judgments, repair limits and budgets otherwise match.
No policy variants or score tuning are performed after smoke outcomes are observed.

## Judgment and bounded repair

The judge gets a fresh chat invocation containing the original request and a
deterministically rendered journey with every scheduled call, mode, trip, route,
segment, time, connection wait and transfer count. It does not see formulas,
votes, selector identity, preferred labels or reference annotations. Return
`satisfied`, `violated`, or `uncertain`, with request spans and brief explanation.
Malformed judgments become uncertain and remain logged. A fresh invocation from
the same model is not an independent oracle; model identity sharing is recorded.

Definite judgments eliminate inconsistent candidates. Uncertainty eliminates none;
an uncertain witness is not repeatedly queried. At most two judgments and one repair
are allowed. D/E repair only when every candidate is eliminated, using the same
initial interpretation and concrete feedback. Accept a repair only if it agrees
with every definite judgment. Opposite definite labels on the same journey produce
an explicit contradiction and no repair. Candidate exhaustion, no witnesses,
budget exhaustion, timeouts and unresolved ties stay visible. Stable generation
order selects among survivors. Unresolved methods can return a diagnostic plan,
but it is never labeled proven correct. The initial output is retained for damage
analysis; hidden labels never choose an output.

Only offline evaluation and a separately identified diagnostic module can load
reference labels. The ordinary runner rejects any non-model judgment mode.

## Baselines and attribution

| Method | Working implementation | Relationship to prior work |
|---|---|---|
| A | One structured translation and solver | Standard formalization baseline |
| B | A plus ordinary source-based critique and at most one rewritten interpretation | Bounded self-critique; can damage a correct draft |
| C | Alternating concrete satisfying/violating pool examples of the first interpretation, independently judged against the request; repair on inconsistency | SSV-inspired positive/negative example adaptation, not reproduction |
| D | Unweighted pair separation and bounded judgments/repair | ARTEMIS-inspired balanced selection adaptation, not reproduction |
| E | Pair separation weighted by `1+I_ij` | Proposed decision-consequence increment |

Original SSV generates model instantiations and checks them against formalizations,
including reasoning answer options. C reverses instance production: exact pool
evaluation supplies instances and a model labels their correspondence with source
intent. It omits option-specific checks and cannot inherit SSV verification claims.
Original ARTEMIS uses temporal-logic specifications, fragment/proxy trace generation
and human validation. D uses complete finite journey examples and automated model
judgments; no claim of reproducing its trace complexity or human-effort results.

Translations are shared through identical prompt/model/seed keys. The same witness
judgment can be replayed across D/E. Every method is charged each logical call it
would make independently, including cached calls. Actual generation attempts,
failures, tokens, latency and GPU session time are separately recorded. A/B/C use
fewer initial samples as specified; D/E are the critical controlled comparison.

## Scope of claims and next evaluation

Candidates can omit the correct interpretation or share an error. A completed
no-witness check establishes equivalence only in the finite pool. Model agreement
and source spans are fallible evidence. No central mechanism here claims novelty
for LLM+solver composition, multiple interpretations, distinguishing examples,
balanced queries or counterexample-guided repair. See the verified overlap analysis
in [literature.md](literature.md); it is a targeted search, not exhaustive novelty verification.

The primary outcome is complete satisfaction of independently specified requirements
by returned plans. Report infeasible requests separately, including correct and false
infeasibility. Secondary measures include invalid plans, unresolved outputs/coverage,
repair damage, error categories, calls/tokens, solver/wall time and GPU use.
Annotations are provisional until human review. Natural model errors are distinct
from injected fixtures. Preserve ties, unnecessary validation and harmful repairs.

Six OD base groups contain all five requirement variants and their two textual
forms together: groups 00–03 development, 04 validation, 05 held out. This versioned
rule is deterministic. The second textual form is an assistant-authored prefix
variation, not diverse model paraphrasing. Routes, geography, entities and dates
still overlap substantially. Future held-out groups should add dates/corridors.
Stage 1 rejects held-out inference. The smoke subset is one development group,
so it supports no independent-group confidence interval or advantage claim.

For a later pilot, pair D/E by base group with common translation samples and seeds.
Average variants/replicates within groups; bootstrap paired group differences
(2,000 resamples, fixed seed), and report absolute rates and intervals. Never treat
paraphrases, witnesses or repeated generations as independent passengers/requests.
Freeze prompts, pool bounds, policy, budget grid and adjudicated labels before the
publication-scale held-out run. That run is outside Stage 1 authorization.
