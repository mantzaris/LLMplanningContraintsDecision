# Stage 2 mechanism diagnosis — CPU only

**Validation improved the initial result, but consequence weighting did not improve
on balanced selection. The rare differences are explained by the scoring algebra,
the observed candidate sets, and the available services; no implementation defect
was found that forces D/E equivalence.** The proposed time-value follow-up addresses
an engineering weakness in model output, not a demonstrated new research contribution.
The next justified action is a **CPU-only annotation and data-coverage gate before
further inference**, rather than another GPU run on these inspected requests.

This diagnosis starts at `06cefbc0eacf28350b3a3683cc1944b9ae9589a7` on clean `main`.
The [GPU report](STAGE2_GPU_EXECUTION.md), frozen configuration, implementation,
raw bundles/calls, ordinary and oracle outputs, and ledgers were inspected. All
152 hashed raw-run JSON/JSONL files matched the saved manifest. All 48 pairs were
replayed again under their recorded source revision. No primary code, prompts,
references, universe, scores, model outputs or historical result was changed.

**New GPU usage: zero generations and zero seconds.** Historical Stage 2 remains
358 generations and 681.6209 measured seconds plus ≤30 seconds; cumulative usage
remains 404 generations and 919.0111 measured seconds plus ≤60 seconds. The stage
ledger hash is unchanged before/after this audit. All statements below concern these
48 inspected development bases, one replicate each, not fresh holdout evidence.

## 1. Budget zero versus validation

The table distinguishes correctness from merely returning an output. Infeasibility
is conditional on the declared pool. Invalid model output, unresolved output, and
infrastructure failure remain separate.

| Method | Budget | Correct | Valid feasible | Invalid plan | False infeas. | Correct infeas. | Invalid output | Unresolved | Timeout/infra | Judgments |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 0 | 31/48 | 28/40 | 5 | 6 | 3/8 | 6 | 0 | 0 | 0 |
| D = E | 0 | 31/48 | 28/40 | 5 | 7 | 3/8 | 5 | 0 | 0 | 0 |
| D = E | 1 | 33/48 | 30/40 | 5 | 5 | 3/8 | 5 | 0 | 0 | 25 |
| D = E | 2 | 33/48 | 30/40 | 5 | 5 | 3/8 | 5 | 0 | 0 | 29 |
| D = E | 4 | 33/48 | 30/40 | 5 | 5 | 3/8 | 5 | 0 | 0 | 29 |

A uses one translation per request (48 logical calls); D/E budget 0 use four
(192 logical calls) and choose the first valid interpretation after deduplication.
Their correct-request sets are identical at budget 0. A has six invalid outputs
and six false infeasibility reports; D/E have five and seven. In `pilot-09`, A's
first raw response is malformed JSON, while the additional translations provide
a syntactically valid but wrongly infeasible interpretation. More candidates
therefore change that error category without recovering correctness.

At budgets 1/2/4 both selectors resolve **33/48 (68.75%)**, versus **31/48 (64.58%)**
at budget 0: a net gain of two requests, **4.17 percentage points**. Each has three
improvements and one deterioration:

| Request | Budget 0 → budget 1, both methods | Mechanism |
|---|---|---|
| `pilot-12` | False infeasibility → valid plan | Correct positive example removes an invented, impossible departure bound |
| `pilot-24` | Invalid plan → valid plan | Correct negative example removes wrong lower-bound interpretations; a latest-departure alternative remains |
| `pilot-25` | False infeasibility → valid plan | Correct example removes wrong intermediate-stop/order interpretations |
| `pilot-14` | Valid plan → false infeasibility | Correct negative label removes formulas whose selected plans happened to be valid; all available interpretations are wrong |

`pilot-27` also changes **false infeasibility → invalid plan**. This is not a
correctness improvement. The 15 wrong requests at budget 1 stay wrong at budgets
2 and 4. Fourteen were wrong at every budget: pilot-01, pilot-02, pilot-05, pilot-09, pilot-15, pilot-19, pilot-22, pilot-23, pilot-27, pilot-33, pilot-34, pilot-35, pilot-40, pilot-41. The exception,
`pilot-14`, was initially correct and was damaged by validation.

Each method makes 25 judgments at budget 1 and 29 at budgets 2/4. The extra second
queries are D: `06,20,34,37`; E: `00,06,20,34` (all IDs have the `pilot-` prefix).
**No selected plan changes between budgets 1 and 2**, not merely no change in the
aggregate rate. These queries narrow candidates; they do not improve final plans.
In `pilot-34`, the second wrong judgment discards the candidate that could have
recovered the already incorrect result. Budgets 2→4 execute **zero additional
ordinary judgments**. There is no timeout or call-budget exhaustion behind the flat curve.

| Budget | No parsed candidate | One class / no witness | Budget cap with witnesses left |
| --- | --- | --- | --- |
| 0 | 5 | 18 | 25 |
| 1 | 5 | 39 | 4 |
| 2 | 5 | 43 | 0 |
| 4 | 5 | 43 | 0 |

The state-at-budget reasons in this table apply to both methods; four requests have
witnesses left at budget 1, though one request ID differs between D and E. At budget
2 every parsed bundle has one remaining semantic class. No primary D/E repair runs,
no all-candidate elimination, and no uncertain or contradictory judgment occurs.
The raw terminal event is `no_distinguishing_witness_in_completed_pool`; the audit
separates its single-class cause from a hypothetical exhausted-witness case with
multiple remaining classes. The latter does not occur here.

The separate saved-bundle oracle resolves **31, 34, 35, 35** at budgets **0,1,2,4**
for both methods. It uses D judgment counts **0,25,28,28**, E **0,25,29,30**.
Correct oracle labels recover five initial failures and damage `pilot-14`; the
extra E query between budgets 2 and 4 improves neither correctness nor final plan.

## 2. Why the selectors usually agree

All 48 bundles are tabulated in [all-bundles.csv](../artifacts/stage2/mechanism-v1/all-bundles.csv).
It includes requested/parsed counts, exact text and canonical duplicates, semantic
classes, journey acceptance patterns, pair weights, distinct witness partitions,
full D/E rankings, top ties, selected sequences, and stopping states at 0/1/2/4.
[bundles.json](../artifacts/stage2/mechanism-v1/bundles.json) adds the state before
every actual query, candidate formulas/plans, and the elimination transitions.

An **acceptance pattern** is the Boolean vector of candidate judgments on a journey.
A **witness partition** identifies that vector with its complement: both separate
exactly the same candidate pairs. This is different from the candidate's own
acceptance vector over all journeys. Counts below refer to the frozen pool.

| Mutually exclusive initial state | Bundles | Implication |
| --- | --- | --- |
| No parsed interpretation | 5 | No selector operates |
| One semantic class | 18 | No witness |
| Two classes | 18 | One pair / one cut partition |
| 3+ classes, uniform weights | 3 | E is a positive scalar multiple of D |
| Nonuniform, same first choice | 2 | pilot-06 and pilot-24; shared top-ID tie resolution |
| Nonuniform, different first choice | 2 | pilot-00 and pilot-37 |

These six rows are mutually exclusive and sum to 48. Other useful counts overlap:

| Sufficient condition or observed agreement | Bundles | Interpretation |
|---|---:|---|
| Uniform consequence weights, with witnesses | 21 | Includes all 18 two-class bundles and three larger bundles |
| All witnesses induce one unordered partition | 18 | The same 18 two-class bundles; not an additional independent cause |
| Scores differ but the full ranking is preserved | 14 | A positive common multiplier changes values, not order or ties |
| Equal scores across methods, with witnesses | 7 | Pair impact is zero; selected plans do not cross-violate |
| Same first choice with a shared top-score tie | 21 | Shared deterministic journey-ID ordering resolves both top sets |
| Different full ranking but same first choice | 2 | `pilot-06`, `pilot-24` |
| Different first choice / sequence | 2 / 2 | `pilot-00`, `pilot-37` |
| No initial query | 23 | 18 one-class bundles plus five with no parsed candidate |
| Multiple classes but no unused witness at the final state | 0 | Terminal parsed states have one class |
| Coding defect preventing intended weighting | 0 found | Recomputed scores, plans and exact replay agree |

There are **192 requested/returned translations**, 160 parsed, eight identical-text
repetitions, 43 canonical duplicates, 117 canonical formulas, and 77 semantic classes.
Forty additional syntax variants collapse through pool equivalence. Partition counts
per bundle are: zero in 23, one in 18, two in five, and three in two. Thus 1,237
available witness memberships encode only **34 distinct within-bundle cut partitions**.
Witness count alone substantially overstates choice diversity.

### Sufficient conditions for this implementation

For active candidates H and witness x, let K(x) be the unordered pairs separated by
its Boolean acceptance vector, c(x)>0 the shared cost, and w_ij=1+I_ij. The implemented
scores are

S_D(x)=|K(x)|/c(x), and S_E(x)=Σ_{ij in K(x)}w_ij/c(x).

The primary cost is one; sorting uses exact rational scores, then ascending journey
ID. Candidate plans and pair weights do not change when unrelated candidates are
removed. For this finite implementation:

1. **No distinct pair:** zero/one semantic candidate gives no witness for either method.
2. **Uniform positive weights:** if all active-pair weights equal w, S_E=w*S_D.
   Rankings and ties are identical even with unequal shared positive witness costs.
   This includes the two-candidate case, which has only one pair.
3. **One cut partition:** if all available witnesses have the same K, their two
   numerators are each constant. Both rank by inverse cost and the same ID tie rule.
   With globally distinct candidate vectors and completed definite-label checks, a
   single available partition here corresponds to two classes; do not double-count it.
4. **Common top under the tie rule:** if the smallest-ID member of each method's
   maximum-score set is the same journey, the next choice agrees even when lower
   rankings differ. Whole sequences agree only if this condition continues after
   every shared judgment/update. Uniform initial weights guarantee their uniformity
   in surviving subsets; a coincident first choice by itself does not.

With complete pool signatures and definite binary judgments, a distinguishing query
removes at least one candidate and retains at least one. Surviving candidates agree
on previously judged journeys, so any remaining disagreement has an unused witness.
With n initial classes there can be at most n−1 such elimination queries. Therefore
with at most four classes a fourth ordinary definite-label query is unnecessary in
this setting, even though the cap is four. Uncertain judgments would break this
bound; there are none in the pilot.

Two focused tests exhaust **324 tiny candidate-matrix/cost systems**, independently
compute cut scores, and check these equivalence conditions against the implementation.
All 77 selected candidate plans also match an exact finite-pool scan independent of
the Z3 search. These checks support the stated finite conditions, not a theorem about
arbitrary selection objectives or language-model interpretation quality.

### The 18 consequential bundles

Of the 18 bundles with a positive cross-plan impact, **11 have two classes** and
**three larger bundles have uniform weights** (`14,20,34`). This leaves only four
nonuniform opportunities (`00,06,24,37`). In `06` and `24`, D ties all 64 witnesses;
E's best-score set contains 59, including D's smallest-ID witness. After the same
first judgment, `06` has two classes and `24` has one: the remaining sequence is
forced to agree. Only `00` and `37` choose differently. The observed 2/18 is thus
fully accounted for without changing weights, introducing candidate errors, or
selecting favorable cases.

## 3. Both divergent cases

The full two-case reconstruction is in
[divergent-cases.json](../artifacts/stage2/mechanism-v1/divergent-cases.json): original
requests, every candidate formula/plan, all ranked witness IDs and scores, judgments,
updates, final formulas/plans, and independent ordinary/oracle outcomes. Full scheduled
journeys remain in the preserved source run and are recoverable by ID using the
existing renderer; no timetables or full schedule-bearing prompts are republished.

### `pilot-00`: different choice, identical plan, extra E query

Original request: “On 2026-09-14, plan the outbound journey from NW 5th & Davis
[stop_id=9301] to SW 5th & Columbia [stop_id=7594]. Depart no earlier than 08:25:17
and arrive by 09:30:25, both inclusive.” Reference bounds are **30317 and 34225 seconds**.

| Candidate | Predicted departure ≥ / arrival ≤ seconds | Selected plan | Reference-valid selected plan |
|---|---|---|---|
| c0 | 30177 / 35425 | `0e81a91bb035a1d8574d` | Yes |
| c1 | 302517 / 354025 | No plan; infeasible in pool | — |
| c2 | 30097 / 34202 | `0e81a91bb035a1d8574d` | Yes |

No candidate is reference-equivalent. c0/c2 share a selected plan, so their impact
is zero; both pairs with c1 have impact one. E weights are **2,1,2**.

| Witness | Acceptance (c0,c1,c2) | D score | E score | Reference / model label |
|---|---|---:|---:|---|
| `002ee67351572c9abe93` | 1,0,0 | 2 | 3 | Satisfied / satisfied |
| `00b30b64cd73de674651` | 1,0,1 | 2 | 4 | Satisfied / satisfied |

D's top tie contains all 16 witnesses; E's contains seven. D picks the first row,
retaining c0 immediately. E picks the second, retaining c0/c2, then asks the first
row and retains c0. There are no repairs. Both ordinary and oracle runs end with
the same valid plan and the same incorrect formula. The practical difference is an
extra E judgment, not a correctness or planning-objective improvement.

### `pilot-37`: correctness tie conceals an inferior E plan

Original request: “On 2026-09-14, plan the outbound journey from NW Everett & 5th
[stop_id=8886] to N Williams & NE Weidler [stop_id=11480]. Do not use rail or tram.
Depart no later than 08:57:49, inclusive. Make at most 1 transfers.” The latest
bound is **32269 seconds**; mode exclusion and transfer constraints are correctly
copied by these candidates.

| Candidate | Departure constraint | Selected plan | Pool-reference equivalence |
|---|---|---|---|
| c0 | depart_le 31499 | `4e0b535d27d1f3fa24fe` | No |
| c1 | depart_le 32279 | `4e0b535d27d1f3fa24fe` | Yes, despite a ten-second numeric error |
| c2 | depart_ge 31729 | `4a89a06ba5058ef4ccea` | No |
| c3 | depart_le 32249 | `4e0b535d27d1f3fa24fe` | No |

Impacts in pair order (01,02,03,12,13,23) are **0,2,0,1,0,2**. Pairs among c0/c1/c3
have no selected-plan consequence; E concentrates on separating c2 from them.

| Selected witness | Accepted candidates | D score | E score | Use |
|---|---|---:|---:|---|
| `3ec28069888f5177b261` | c1,c3 | 4 | 7 | D first; model correctly satisfied |
| `022c2a4af86602d54884` | c0,c1,c3 | 3 | 8 | E first; model incorrectly violated |
| `4a89a06ba5058ef4ccea` | c1 among D's remaining c1/c3 | 1 | 1 | D second; correctly satisfied |

D's initial top tie has seven witnesses; E's has 58. D retains c1/c3, then c1. E's
judge reverses the meaning of a latest-departure bound and invents a second transfer;
its false negative retains c2 alone. Both returned plans satisfy the actual request,
but **E arrives 6,366 seconds (106 minutes 6 seconds) later than D** with the same
number of boardings. This is a descriptive loss under the common planning objective,
not a retrospective change to the primary correctness endpoint.

With correct oracle labels E retains c0/c1/c3 after its first query, then takes two
more queries to reach c1. D takes two total. Both recover the same pool-equivalent
interpretation and earliest selected plan. Thus these choices are not equally efficient
under perfect judgments, and the ordinary E choice also exposes a harmful judge error.
No claim of a population effect follows from this one case.

## 4. Every remaining failure and every wrong judgment

The following table covers all 15 incorrect resolutions at the main budget. It is
assistant trace analysis, not human annotation. A “missing interpretation” label alone
is insufficient: each row identifies the actual modeled requirement failure or
update that explains the decision. No D/E model repair was performed.

| Request | Ordinary / oracle, budget 4 | Diagnosis |
| --- | --- | --- |
| pilot-01 | incorrect_plan / false_infeasibility | Latest departure became depart_ge, with wrong numbers. The wrong satisfied label keeps an invalid plan; oracle instead returns false infeasibility. Value-only binding cannot correct the operator. |
| pilot-02 | false_infeasibility / false_infeasibility | All raw variants reject the pool because their visit requirements are wrong. Source timing normalization cannot fix the visit lists; oracle has no witness. |
| pilot-05 | invalid_model_output / invalid_model_output | All four outputs reject supported time operations. The requested same-day contradiction is intentional; no parsed AST exists for value-only repair. |
| pilot-09 | false_infeasibility / false_infeasibility | 09:39:47 is 34787 seconds, not 35947. The first output also contains a JSON comment. Three parsed copies agree on the wrong infeasible bound. |
| pilot-14 | false_infeasibility / false_infeasibility | All variants turn a latest bound into an earliest bound. A correct negative witness label removes candidates with valid selected plans and leaves false infeasibility, including under oracle labels. |
| pilot-15 | invalid_model_output / invalid_model_output | All four outputs reject supported time operations; no parsed AST. The explicit 08:30 departure / 08:00 arrival contradiction is not a reference error. |
| pilot-19 | incorrect_plan / incorrect_plan | The first value 28586 is correct for 07:56:26; other raw variants have wrong values. All use depart_ge instead of depart_le. One semantic class selects a late plan; value-only normalization cannot fix the direction. |
| pilot-22 | false_infeasibility / false_infeasibility | Return-only wording is accompanied by an invented outbound bound, e.g. depart_ge 34500. Correcting the return value 32500 to 33900 leaves the added outbound restriction and false infeasibility. |
| pilot-23 | invalid_model_output / invalid_model_output | Four unsupported reports for supported time atoms; the deliberately infeasible conjunction remains representable. No parsed formula to normalize. |
| pilot-27 | incorrect_plan / false_infeasibility | Return 09:40:00 is 34800 seconds; candidates use 35400 or 5840, among other values. A wrong positive label chooses a too-early return; oracle chooses false infeasibility. Value-only sensitivity recovers a valid initial plan. |
| pilot-33 | invalid_model_output / invalid_model_output | Four unsupported reports, not an infrastructure failure or proof of infeasibility. Clock conversion alone cannot recover a missing formula. |
| pilot-34 | incorrect_plan / correct_feasible_plan | 08:42:07 is 31327 seconds. The pool-equivalent c3 alternative exists despite its 31247 value; the second wrong label removes it. Correct oracle labels recover the request; value normalization also fixes the initial plan. |
| pilot-35 | incorrect_plan / incorrect_plan | Return 09:16:00 is 33360 seconds; c0 uses 3696. Different formulas all accept the same pool and select an early return. Value-only sensitivity fixes the initial plan. |
| pilot-40 | false_infeasibility / correct_feasible_plan | A pool-equivalent, valid-plan alternative exists. The judge incorrectly says 09:42 is earlier than 09:12 and eliminates it. Normalizing the return number does not remove c0's invented outbound bound; correct oracle judgment is still needed. |
| pilot-41 | invalid_model_output / invalid_model_output | All four outputs incorrectly report supported departure/arrival operations unsupported. No AST exists; this is not an arithmetic compiler bug. |

Five requests (`05,15,23,33,41`) have no parsed candidate because the model claims
supported time operators are unsupported. Eight remaining oracle failures have
parsed candidates: `01,02,09,14,19,22,27,35`. Their causes include reversed inequalities,
wrong visits, numeric encoding, invented outbound restrictions, and the loss of a
fortuitously valid plan. **All 13 oracle failures lack an equivalent interpretation,
but absence is a coverage symptom, not a sufficient causal explanation by itself.**
`pilot-14` in particular has valid candidate-selected plans and is damaged despite
correct witness labels. Conversely, 12 ordinary final plans are correct despite no
reference-equivalent candidate: full formal equivalence is not necessary for a
valid selected plan.

Seven distinct judgment invocations are wrong, used 13 times logically across D/E:

| Request / query | Journey ID | Wrong verdict → reference | Methods / downstream effect |
| --- | --- | --- | --- |
| pilot-01/1 | 4f068e23d6f9f80811f2 | satisfied → violated | Both retain an invalid plan. Correct label changes it to false infeasibility; no correct resolution is available from the candidates. |
| pilot-06/1 | 01d5cd87319e366359a7 | satisfied → violated | Both remove an alternative but keep the same valid selected plan; harmless to primary outcome. |
| pilot-06/2 | 06b5d39e855ca24bde86 | violated → satisfied | Both keep the same valid plan despite a second wrong label; no primary loss. |
| pilot-27/1 | 001aadd047bd2fdc8a79 | satisfied → violated | Both switch false infeasibility to an invalid plan. Oracle remains falsely infeasible: no useful candidate-selected plan. |
| pilot-34/2 | 004c05afb1f5827ae3be | satisfied → violated | Both eliminate the useful pool-equivalent candidate. Correcting this label after the identical first step recovers the request. |
| pilot-37/1 | 022c2a4af86602d54884 | violated → satisfied | E alone removes the equivalent candidate. Final plan is valid but arrives 6366 seconds later than D. Primary tie; objective harm. |
| pilot-40/1 | 008b1d441a8449cba7fe | violated → satisfied | Both eliminate the valid alternative. Correcting the sole label recovers the request. |

Only `34` and `40` represent recoveries blocked solely by the relevant wrong judgment
in an otherwise shared ordinary/oracle prefix. In `01` and `27`, correcting the label
changes the kind of wrong output without producing a correct resolution; candidate
coverage is independently limiting. The two `06` errors are harmless to final-plan
correctness. `37` is harmless to primary correctness but harmful to the planning
objective. Shared cached calls are not independent observations.

### Annotation and implementation uncertainty

The independent narrow wording parser agrees with all 48 reference dictionaries;
all ten returned incorrect plans/false infeasibility reports have explicit trace
explanations. The other five are invalid interpretations. There is no identified
ambiguous bound, incorrect reference label, date/timezone/service-day defect,
midnight defect, compiler defect, solver timeout or infrastructure failure in these
records. **This is absence of evidence in this audit, not human validation or proof
that such defects never occur.** References remain provisional. For most wrong numeric
outputs, extraction and arithmetic are not separately observable from the final JSON.
The arithmetic attempt is explicit in `pilot-09`'s malformed raw comment, which labels
35947 as “09:39:47 in seconds.”

Date and timezone are public facts outside the predicted DSL, and all pilot journeys
are on the declared morning service day. Beyond-midnight parsing exists and its
focused checks remain valid, but no fresh pilot instance tests a midnight or DST
boundary. Unsupported raw responses that mention timezone offsets do not establish
a timezone implementation error.

## 5. What the time-conversion proposal would actually fix

The existing GTFS clock parser computes `HH*3600 + MM*60 + SS` correctly. The prediction
parser preserves valid integer values; it does not perform a faulty timezone or unit
conversion. The errors are already present in raw model output. No deterministic
implementation bug was found that justifies rewriting historical runs.

| Category | Finding |
|---|---|
| A. Deterministic implementation bug | None identified; parsed candidate plans match exact pool evaluation |
| B. Model extracts/encodes an explicit time incorrectly | Nine failed bundles contain a wrong number in at least one raw variant, sometimes alongside wrong operator/scope; extraction versus arithmetic often unidentifiable |
| C. Genuine timing ambiguity | None identified in the explicit template bounds; annotation remains provisional |
| D. Reference error | Independent grammar and arithmetic agree with all references; no identified correction |
| E. Request/universe mismatch | Some clauses are vacuous or intentionally infeasible in the bounded services; this limits what examples can reveal, not seconds arithmetic |

The table exposes the text, raw parsed numeric atoms, source/reference value and
planning effect for every remaining failure with an explicit time requirement.
Operator or scope changes are deliberately not called “conversion.”

| Request | Original timing text | Predicted seconds atoms (all parsed variants) | Independent source/reference seconds | Value-only initial result |
| --- | --- | --- | --- | --- |
| pilot-01 | Depart no later than 09:08:00 | outbound:depart_ge=33480; outbound:depart_ge=33680; outbound:depart_ge=34080 | outbound:depart_le=32880 | incorrect_plan → incorrect_plan |
| pilot-05 | Depart no earlier than 08:30:00; arrive by 08:00:00 | No parsed AST | outbound:depart_ge=30600; outbound:arrive_by=28800 | invalid_model_output → invalid_model_output |
| pilot-09 | depart no earlier than 09:39:47 | return:depart_ge=35947 | return:depart_ge=34787 | false_infeasibility → correct_feasible_plan |
| pilot-14 | Depart no later than 07:28:14 | outbound:depart_ge=26204; outbound:depart_ge=262814; outbound:depart_ge=26546 | outbound:depart_le=26894 | correct_feasible_plan → correct_feasible_plan |
| pilot-15 | Depart no earlier than 08:30:00; arrive by 08:00:00 | No parsed AST | outbound:depart_ge=30600; outbound:arrive_by=28800 | invalid_model_output → invalid_model_output |
| pilot-19 | Depart no later than 07:56:26 | outbound:depart_ge=27986; outbound:depart_ge=28186; outbound:depart_ge=28226; outbound:depart_ge=28586 | outbound:depart_le=28586 | incorrect_plan → incorrect_plan |
| pilot-22 | depart no earlier than 09:25:00 | outbound:depart_ge=34500; return:depart_ge=32500; return:depart_ge=34500 | return:depart_ge=33900 | false_infeasibility → false_infeasibility |
| pilot-23 | Depart no earlier than 08:30:00; arrive by 08:00:00 | No parsed AST | outbound:depart_ge=30600; outbound:arrive_by=28800 | invalid_model_output → invalid_model_output |
| pilot-27 | depart no earlier than 09:40:00 | return:depart_ge=35400; return:depart_ge=5840; return:depart_ge=58800 | return:depart_ge=34800 | false_infeasibility → correct_feasible_plan |
| pilot-33 | Depart no earlier than 08:30:00; arrive by 08:00:00 | No parsed AST | outbound:depart_ge=30600; outbound:arrive_by=28800 | invalid_model_output → invalid_model_output |
| pilot-34 | Do not depart before 08:42:07 | outbound:depart_ge=31247; outbound:depart_ge=31647; outbound:depart_ge=3207; outbound:depart_ge=32407 | outbound:depart_ge=31327 | incorrect_plan → correct_feasible_plan |
| pilot-35 | depart no earlier than 09:16:00 | return:depart_ge=3696; return:depart_ge=5772 | return:depart_ge=33360 | incorrect_plan → correct_feasible_plan |
| pilot-40 | depart no earlier than 09:12:00 | outbound:arrive_by=86400; outbound:depart_ge=32400; outbound:depart_ge=3432; return:depart_ge=3240; return:depart_ge=32760; return:depart_ge=3492 | return:depart_ge=33120 | false_infeasibility → false_infeasibility |
| pilot-41 | Depart no earlier than 08:30:00; arrive by 08:00:00 | No parsed AST | outbound:depart_ge=30600; outbound:arrive_by=28800 | invalid_model_output → invalid_model_output |

### One source-only CPU sensitivity check, not a new GPU experiment

A diagnostic function binds an **existing** time atom to a **unique explicit** request
clock with the same operator and scope, then replaces only its integer value. It
reads request text and the parsed AST, **not reference constraints**. It never adds
an atom, repairs JSON, changes an inequality or scope, deletes an invented bound,
or guesses among repeated bindings. Unmatched/ambiguous atoms are left unchanged.
Two focused tests also check that these boundaries are respected and inputs are not
mutated. The function is confined to the offline diagnosis script.

Across the inspected corpus this changes 116 values in 93 parsed interpretations,
covering 27 bundles. This is a posthoc, template-specific sensitivity analysis of
saved outputs, not an estimate on new language or a run of the proposed HH:MM:SS
model-generation arm.

| Diagnostic endpoint | Historical | Value-only sensitivity | Interpretation |
|---|---:|---:|---|
| A, initial single translation + solver | 31/48 | 34/48 | Source-only replacements recover `27,34,35`; malformed first response in `09` remains invalid |
| D/E initial four-candidate output | 31/48 | 35/48 | Recovers `09,27,34,35`; no initial correctness damage |
| D/E with privileged oracle judgment, budget 4 | 35/48 | 38/48 | Separately labeled oracle; additional recoveries over historical oracle are `09,27,35` |
| Ordinary D/E judgment after changed candidate generation | — | **Not run / not estimated** | New selected witnesses may lack saved ordinary model judgments |

Thus **four of the 15 main failures** are demonstrably addressable at the initial-plan
level by value replacement. `22` and `40` also contain bindable wrong return numbers,
but extra outbound constraints keep the initial result wrong. `01` and `14` need
inequality repair; `19` already has the correct number in its first variant, but all
its variants use the wrong inequality. The five unsupported cases
need actual supported formalizations, not arithmetic. Recovery from a new LLM
HH:MM:SS interface is **speculative** until independently tested: the model could
still extract the wrong literal, invert scope, or declare the formula unsupported.

Correct oracle labels were used only to assess or replay privileged branches, never
to choose a value or insert a correct alternative in the source-only function. The
38/48 figure must not be described as ordinary model-judged performance. No hidden
reference-based “best candidate” selection occurred.

A deterministic literal-normalization baseline is simpler than another LLM invocation.
The existing offline review grammar can already recover all reference rules from
these tightly templated requests, emphasizing how weak this corpus is as evidence
for a separate LLM normalization contribution. General natural-language extraction
remains harder, but the current record does not establish novelty or necessity for
an additional LLM mechanism. Any later candidate change must supply identical bundles
to D/E and report candidate-quality gains separately from selector gains.

## 6. Does the universe suppress the question?

The frozen feed, route subset and public metadata were retained. A **CPU-only pool
sensitivity audit** removed only the segment/joint caps, with bounds 2,000/100,000
chosen from public enumeration counts (maximum segment count 1,047; largest segment
count product 65,296) before this comparison. It completed exhaustive enumeration
under the unchanged two-ride, same-stop, timing and connection rules. All original
journeys remain in the expanded sets. This is not a replacement primary universe.

| Quantity | Frozen | Uncapped sensitivity |
|---|---:|---:|
| Journey memberships | 4,366 | 77,871 |
| Distinct candidate classes, sum across bundles | 77 | 77 |
| Distinct witness partitions, sum across bundles | 34 | 34 |
| Bundles acquiring a candidate class / partition | — | 0 / 0 |
| Reference-equivalent candidate coverage | 23/48 | 22/48 |
| Nonuniform initial consequence weights | 4/48 | 5/48 |
| Different initial D/E choices | 2/48 | 2/48 |

Uncapped nonuniform-weight cases: pilot-00, pilot-06, pilot-24, pilot-34, pilot-37. Uncapped differing
first choices: pilot-00, pilot-37. No new model judgments or comparative correctness
experiment was run in the expanded domain. `pilot-39` loses its apparent reference
equivalence when more scheduled departures are included. Additional journeys can
change weights, plans and equivalence to the reference without adding a distinction
between any two saved candidate formulas. **Increasing the caps alone is not the
promising next change.**

Clause effects measure each independently specified requirement over the entire
public pool, not a pool pruned by the other reference clauses:

| Requirement | Clauses | Frozen always true | Always false | Varies | Uncapped always true | Always false | Varies |
| --- | --- | --- | --- | --- | --- | --- | --- |
| allowed_modes | 8 | 8 | 0 | 0 | 8 | 0 | 0 |
| earliest_departure | 29 | 7 | 0 | 22 | 7 | 0 | 22 |
| forbidden_modes | 11 | 8 | 3 | 0 | 8 | 3 | 0 |
| latest_arrival | 13 | 0 | 0 | 13 | 0 | 0 | 13 |
| latest_departure | 8 | 0 | 0 | 8 | 0 | 0 | 8 |
| ordered_calls | 8 | 7 | 0 | 1 | 7 | 0 | 1 |
| transfer_limit | 24 | 18 | 0 | 6 | 18 | 0 | 6 |

Of 101 clauses, **48 are always true, three always false and 50 vary**. The same
classification holds after uncapping. All 48 always-true clauses also have zero
marginal exclusion effect in their conjunction. Among the 40 feasible requests,
only **40/88 clauses (45.45%)** are nonvacuous. In particular:

- Every ride is a bus: all rail/tram exclusions and bus-only permissions are vacuous;
  the three “do not use buses” requests are intentionally infeasible in this domain.
- A public maximum of two rides per segment makes 18 transfer-limit clauses vacuous.
  Six clauses distinguish zero from one transfer; no journey can test allowing one
  versus two transfers in a segment.
- Seven of eight ordered-visit requirements hold on every available journey. Corridor
  topology and retained intermediate calls, not merely truncation, suppress alternatives.
- Seven earliest-departure bounds are vacuous even without caps. Other temporal bounds
  vary, but their variants commonly create nested acceptance sets and uniform impacts.

This does not invalidate the conditional primary results. It does limit what the
current data can say about semantic validation across timing, modes, resources and
scope. Adding synthetic modes/routes to these results would not solve that evidential
problem and was not done.

## 7. Single next action: a data/annotation coverage gate

**Obtain better annotation and data coverage before further inference.** Do not
launch the previously suggested GPU time-conversion arm as a research contribution
on these same requests. Keep deterministic literal normalization as the simplest
engineering baseline for a future independently designed study. Do not automatically
continue the consequence-selection project on the strength of infrastructure or
normalization gains.

The next bounded action is one **CPU-only coverage experiment**, specified here and
not executed in this task:

| Protocol item | Proposed gate |
|---|---|
| Exact hypothesis | The bus-only/two-ride corridor suppresses decision-relevant requirement variation; a real-service universe covering multiple modes and 0/1/2 transfers makes independently worded requirements materially less vacuous |
| One change | Replace the narrow public universe with a coverage-selected real GTFS subset; do not change D/E scores or candidate generation at this gate |
| Simplest baseline | This uncapped bus-only universe, which already rules out truncation as the main cause |
| Objective selection/acquisition rule | First use the full frozen feed. Select a connected subset by published mode diversity and coverage of OD journeys with 0/1/2 transfers, then stop coverage, then stable route/stop IDs. Use only actual published services. If the frozen feed cannot meet the rule, freeze a separately versioned public feed with the existing provenance pipeline; do not select by predicted E wins |
| Fresh data | 24 new base/OD groups, excluding this pilot and Stage 1 groups; six each emphasizing modes, transfers, ordered visits and scoped timing. Include a predeclared 20 feasible / four infeasible mix and eight outbound/return requests. Author/review wording independently after freezing the common public universe; group paraphrases and related scenarios |
| Annotation | Two independent human reviews before calling material audited; unresolved wording stays explicitly provisional. Do not relabel these 48 inspected cases as holdout data |
| Inference budgets | Zero generations for both coverage conditions. No translator, selector or ordinary judge receives reference labels. If a later inference study is separately authorized, D/E must share four-candidate bundles, judging/repair policy and 0/1/2/4 budgets; a candidate change must be applied to both |
| Primary outcome | Fraction of feasible-request clauses that exclude some but not all public journeys; measure each feature family separately. This is a data suitability endpoint, not a plan-correctness or E-improvement claim |
| Practical decision criterion | At least 80% nonvacuous feasible clauses, and at least four feasible requests per feature family with both satisfying and violating journeys. Failure means pause further inference; passing permits a new protocol decision, not automatic GPU execution |
| Compute estimate | **0 GPU seconds, 0 generation requests**. This audit exhaustively handled 77,871 journeys on CPU. For scale only, 24 later four-candidate requests would require 96 translations, about 206 seconds at the saved 2.149 s/translation before any judgments/loading; this is a cost floor, not authorization or a full-pilot forecast |

A common candidate universe must be built from public transport metadata before
request/reference construction. Any deterministic coverage sampling should use public
mode, ride-count and schedule features, not hidden reference constraints or predicted
formulas. Deliberately meaningful coverage is allowed; choosing requests because E
is expected to win is not. Any eventual planning study keeps complete satisfaction
as its primary outcome and evaluates feasible/infeasible requests separately.

The gate is justified by measured vacuity and lack of new partitions under uncapping.
It does **not** promise that E will benefit on broader data. If adequate coverage still
produces mostly equivalent selectors or no cost-adjusted advantage, pausing the
selection-method investigation remains the appropriate conclusion.

## 8. Reproduction, preservation and checks

New compact evidence is in [mechanism-v1](../artifacts/stage2/mechanism-v1/summary.json):
budget outcomes; all 48 ranking/partition/stopping audits; both divergent traces;
all failure/incorrect-judgment records; source-only time sensitivity; and uncapped
pool counts/hashes. Raw model outputs and frozen protocols are unchanged. No new raw
schedule archive is published. The expanded pools are reproducible from the retained
frozen ZIP; their hashes are saved. The source GPU inputs already have verified durable
replicas as documented in the GPU report. New compact diagnostic results are committed
in Git; the new CPU replay repeats those existing saved outputs locally.

Run from the repository root with the existing retained feed and run:

```bash
uv run --frozen python scripts/replay_revision.py --run runs/stage2-pilot-v1 \
  --output runs/stage2-mechanism-v1/replay
uv run --frozen python scripts/stage2_mechanism_diagnosis.py \
  --feed data/raw/trimet-82e6b822de008367b3d3d35bb52545807ea41b6f56623a9aa4b1162b3d54671b.zip \
  --output artifacts/stage2/mechanism-v1
uv run --frozen python scripts/stage2_mechanism_report.py \
  --analysis artifacts/stage2/mechanism-v1 \
  --report reports/STAGE2_MECHANISM_DIAGNOSIS.md
uv run --frozen --extra dev pytest -q tests/test_mechanism_diagnosis.py
```

The report renderer alone works from committed compact audits. It checks the failure
set and records template, script and report hashes. The analysis checks the original
raw-file manifest, recomputes candidate plans, checks every selected witness, repeats
reference wording consistency, and asserts the GPU ledger is unchanged. A changed
diagnostic definition requires a new artifact identity; originals are not overwritten.

Verification: **48/48 exact replay matches; two focused tests pass, covering 324 tiny
matrix/cost systems and the source-only normalization boundary; Ruff passes.** No
correctness patch to ordinary execution was needed, and no corrected primary run is
presented. All counterfactual and oracle results above are explicitly separate from
the historical ordinary 33/48 result.
