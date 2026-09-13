# Stage 2 annotation and transport-coverage closeout

**Pause expansion of the original consequence-weighting method.** This final CPU
audit found **zero clear reference errors and zero unresolved annotation cases under
the documented planning conventions**. No corrected reference or exclusion is
justified. Rescoring 432 saved outputs changed zero categories. The narrow benchmark
limits generalization, but the audit found no material defect warranting a retest.
The existing evidence **fails to support** the claimed advantage over balanced selection.

Starting revision: `7e79d7c7f0e5b960313b1aa60969fa64f161ae36`, clean `main`.
The [mechanism diagnosis](STAGE2_MECHANISM_DIAGNOSIS.md),
[GPU execution report](STAGE2_GPU_EXECUTION.md), and
[historical CPU report](STAGE2_CONTROLLED_PILOT.md) are preserved. The frozen protocol,
48 requests, references, model outputs, and GPU ledgers are unchanged.
**New usage: zero GPU seconds, zero generations, zero external model API calls.**

## Annotation audit

This is **developer/automated consistency checking**, performed by the coding
assistant with local checks, not independent human annotation or adjudication.
All 48 original request texts were read against their references and the
[documented conventions](../docs/data.md). The existing separate wording grammar
was reused; it does not import the constructor or prediction compiler. The audit
also checks public facts that grammar deliberately skips: date, timezone, endpoint
names/IDs, segment windows, active services, and actual saved-journey legality.
The script persists annotation findings **before reading method outputs**.
No preferred plan was used to infer what a request should mean.

The resulting [48-row worksheet](../artifacts/stage2/closeout-v1/annotation-review.csv)
retains the full request, original reference, individual check fields, and blank
human-review fields. In the compact table below, “Agree” covers wording, integer
service-day seconds, inclusive inequalities, and direction; all rows also pass the
date/timezone, entity and public-window checks. Feasibility is an exact count in the
**original pool**, not a claim about every journey in the agency network.

| ID | Family | Wording / time / scope | Visits | DSL | Feasible / pool | Issue |
| --- | --- | --- | --- | --- | --- | --- |
| pilot-00 | timing | Agree | — | Supported | 11/64 | None identified |
| pilot-01 | mode_exclusion | Agree | — | Supported | 4/64 | None identified |
| pilot-02 | ordered_visits | Agree | Agree | Supported | 64/64 | None identified |
| pilot-03 | transfers | Agree | — | Supported | 1/64 | None identified |
| pilot-04 | scope | Agree | — | Supported | 141/256 | None identified |
| pilot-05 | infeasible | Agree | — | Supported | 0/64 | None identified |
| pilot-06 | mode_exclusion | Agree | — | Supported | 35/64 | None identified |
| pilot-07 | ordered_visits | Agree | Agree | Supported | 64/64 | None identified |
| pilot-08 | timing | Agree | — | Supported | 18/64 | None identified |
| pilot-09 | scope | Agree | — | Supported | 18/256 | None identified |
| pilot-10 | infeasible | Agree | — | Supported | 0/64 | None identified |
| pilot-11 | transfers | Agree | — | Supported | 64/64 | None identified |
| pilot-12 | ordered_visits | Agree | Agree | Supported | 64/64 | None identified |
| pilot-13 | timing | Agree | — | Supported | 5/64 | None identified |
| pilot-14 | mode_exclusion | Agree | — | Supported | 22/64 | None identified |
| pilot-15 | infeasible | Agree | — | Supported | 0/64 | None identified |
| pilot-16 | transfers | Agree | — | Supported | 6/57 | None identified |
| pilot-17 | scope | Agree | — | Supported | 31/256 | None identified |
| pilot-18 | timing | Agree | — | Supported | 17/64 | None identified |
| pilot-19 | mode_exclusion | Agree | — | Supported | 45/64 | None identified |
| pilot-20 | ordered_visits | Agree | Agree | Supported | 64/64 | None identified |
| pilot-21 | transfers | Agree | — | Supported | 17/17 | None identified |
| pilot-22 | scope | Agree | — | Supported | 256/256 | None identified |
| pilot-23 | infeasible | Agree | — | Supported | 0/64 | None identified |
| pilot-24 | mode_exclusion | Agree | — | Supported | 14/64 | None identified |
| pilot-25 | ordered_visits | Agree | Agree | Supported | 64/64 | None identified |
| pilot-26 | timing | Agree | — | Supported | 35/51 | None identified |
| pilot-27 | scope | Agree | — | Supported | 35/256 | None identified |
| pilot-28 | infeasible | Agree | — | Supported | 0/64 | None identified |
| pilot-29 | transfers | Agree | — | Supported | 2/64 | None identified |
| pilot-30 | ordered_visits | Agree | Agree | Supported | 31/64 | None identified |
| pilot-31 | timing | Agree | — | Supported | 4/64 | None identified |
| pilot-32 | mode_exclusion | Agree | — | Supported | 30/45 | None identified |
| pilot-33 | infeasible | Agree | — | Supported | 0/64 | None identified |
| pilot-34 | transfers | Agree | — | Supported | 13/64 | None identified |
| pilot-35 | scope | Agree | — | Supported | 168/256 | None identified |
| pilot-36 | timing | Agree | — | Supported | 18/64 | None identified |
| pilot-37 | mode_exclusion | Agree | — | Supported | 59/64 | None identified |
| pilot-38 | ordered_visits | Agree | Agree | Supported | 25/25 | None identified |
| pilot-39 | transfers | Agree | — | Supported | 2/64 | None identified |
| pilot-40 | scope | Agree | — | Supported | 256/256 | None identified |
| pilot-41 | infeasible | Agree | — | Supported | 0/25 | None identified |
| pilot-42 | mode_exclusion | Agree | — | Supported | 28/64 | None identified |
| pilot-43 | ordered_visits | Agree | Agree | Supported | 64/64 | None identified |
| pilot-44 | timing | Agree | — | Supported | 9/25 | None identified |
| pilot-45 | scope | Agree | — | Supported | 204/256 | None identified |
| pilot-46 | infeasible | Agree | — | Supported | 0/64 | None identified |
| pilot-47 | transfers | Agree | — | Supported | 16/25 | None identified |

The following distinctions resolve apparent issues without revising annotations:

- All dates are 2026-09-14, with `America/Los_Angeles` supplied as public context.
  The horizon is 07:00–10:00; return segments are within 09:00–10:00. Equality is
  allowed. No request needs a cross-midnight or cross-timezone interpretation.
- Eight two-segment requests explicitly state scope and endpoint IDs. Movement
  between the outbound destination and return origin is expressly outside the task.
  No implicit walking connection, activity dwell, or extra outbound bound is required.
- Eight visit requests say “remaining aboard counts”; their two ordered stop IDs
  are valid entities. These are scheduled calls, not alight-and-visit activities.
- Five requests (`05,15,23,33,41`, with prefix `pilot-`) deliberately require departure
  at/after 08:30 and arrival by 08:00 on the same morning. They are representable,
  infeasible conjunctions. The model's unsupported responses are not annotation errors.
- Three (`10,28,46`) prohibit buses and are infeasible **in the bus-only pool**.
  They do not establish that the same journey request is infeasible across Portland.

All 40 feasible and eight infeasible labels match the original independent checker.
The seven reference operators have valid representations in the supported DSL; the
audit's expressibility probes never become predicted candidates or method inputs.
All 2,363 distinct saved rides match active trip/route identities and contiguous
published calls, including boarding/alighting permissions. All 4,366 journey
memberships satisfy public endpoints, windows, ride bounds and supported connection
rules. These are checks of the declared scope, not validation of excluded GTFS features.

**Corrections: none. Unresolved wording: none identified within this scope.** The
[versioned correction manifest](../artifacts/stage2/closeout-v1/corrections-v1.json)
records empty correction, uncertainty and exclusion sets. There is no changed-reference
replay to present, and no uncertainty/exclusion-based alternative score was manufactured.
No unresolved case-specific adjudication question remains; the worksheet is available
for later human checking. Correlated construction/review mistakes remain possible:
these annotations retain their **provisional, not human-audited** status.

## Annotation sensitivity and preserved outcomes

Only saved outputs were rescored with the unchanged independently checked references;
no candidates, witnesses or judgments were regenerated. The 432 checks cover A once
per request and D/E at all four budgets. Every category equals its historical value.

| Method | Budget | Original = rescored | Valid plan | Invalid plan | Correct infeas. | False infeas. | Invalid output | Unresolved / infra |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 0 | 31/48 | 28 | 5 | 3 | 6 | 6 | 0 |
| D = E | 0 | 31/48 | 28 | 5 | 3 | 7 | 5 | 0 |
| D = E | 1 | 33/48 | 30 | 5 | 3 | 5 | 5 | 0 |
| D = E | 2 | 33/48 | 30 | 5 | 3 | 5 | 5 | 0 |
| D = E | 4 | 33/48 | 30 | 5 | 3 | 5 | 5 | 0 |

D and E remain **0 wins / 48 ties / 0 losses** against each other at every budget.
Validation improves 31/48 to 33/48: `12,24,25` improve and `14` deteriorates. Feasible
plan validity rises from 28/40 to 30/40; correct infeasibility stays 3/8. The existing
unchanged-reference oracle results remain **31,34,35,35** at budgets **0,1,2,4** for
both methods. Oracle trajectories and the completed mechanism analysis were not rerun.
No annotation correction changes the selector comparison because none was warranted.

## Effective transport coverage

The audit reads the already frozen published TriMet ZIP, SHA-256
`82e6b822de008367b3d3d35bb52545807ea41b6f56623a9aa4b1162b3d54671b`.
It acquires no new data and enumerates no expanded benchmark. Source counts below
refer to the original feed, not current live service. “Active trips” applies the
2026-09-14 calendar; “morning call” means at least one departure in 07:00–10:00.
“BBox-eligible” means two in-bbox morning departure calls on an active trip, not a
demonstration of shared OD alternatives or supported connections between modes.

| GTFS mode | Source routes | Active trips | Trips with morning call | BBox-eligible routes | Selected routes |
| --- | --- | --- | --- | --- | --- |
| bus | 71 | 4727 | 1105 | 24 | 3 |
| gondola | 1 | 384 | 74 | 0 | 0 |
| rail | 1 | 20 | 7 | 0 | 0 |
| tram | 8 | 1022 | 204 | 7 | 0 |

GTFS type 0 (`tram`) includes MAX light rail and Portland Streetcar; type 2 (`rail`)
is WES. Type 6 (`gondola`) is the Portland Aerial Tram, despite its public name.
None of these non-bus services enters the selected routes **2, 4, 17**. Seven type-0
routes already have morning calls within the bounding area; route selection omitted
them. WES and the aerial tram have morning service in the full feed but do not meet
the two-call bbox criterion. Their existence alone proves no feasible multimodal
journey for any pilot request.

For each of the 101 independently specified clauses, the first three effect columns
are exclusive. “Duplicates” counts clauses sharing an acceptance vector with another
clause **in the same request**; “zero marginal” means removing that clause changes no
journey's acceptance by the full conjunction. These two columns overlap the others.
They measure finite-pool equivalence, not duplicate wording or erroneous annotation.

| Constraint | Separates | Always true | Always false | Duplicates* | Zero marginal* | Unsupported |
| --- | --- | --- | --- | --- | --- | --- |
| earliest_departure | 22 | 7 | 0 | 4 | 7 | 0 |
| latest_departure | 8 | 0 | 0 | 0 | 0 | 0 |
| latest_arrival | 13 | 0 | 0 | 0 | 0 | 0 |
| transfer_limit | 6 | 18 | 0 | 11 | 18 | 0 |
| allowed_modes | 0 | 8 | 0 | 7 | 8 | 0 |
| forbidden_modes | 0 | 8 | 3 | 7 | 8 | 0 |
| ordered_calls | 1 | 7 | 0 | 7 | 7 | 0 |

There are **50 separating clauses, 48 always true, and three always false**. The
36 duplicate-clause memberships form 18 pairs, all between always-true clauses;
none is a duplicated nonconstant restriction. All 48 zero-marginal clauses are
always true. Among feasible requests only 40/88 clauses separate journeys.
In 11 requests the entire requirement conjunction accepts every public journey.

| Capability | Actual opportunity and limitation |
|---|---|
| Mode choice | All 19 mode clauses are constant: 16 always true, three always false. The subset cannot test choosing bus versus rail/tram to satisfy a preference. Such requests are expressible, not unsupported. |
| Transfers | 45/48 pools offer both zero- and one-transfer paths in at least one segment; `12,23,43` have only one-transfer paths. 29/48 contain route changes. Of repeated transfer memberships, 1480 change route and 4402 reboard another trip on the same route; both count under the declared vehicle-transfer convention. Only six actual transfer-limit clauses separate journeys; the two-ride ceiling makes at-most-one vacuous and excludes all two-transfer options. |
| Intermediate calls/order | 11/48 pools contain differing stop sets, but only `pilot-30`'s actual visit clause separates journeys. For all eight requested ordered pairs, requiring order excludes zero additional journeys beyond calling at both stops. Thus visits have weak coverage and visit-order choices have none. |
| Direction | Of 16 clauses in eight scoped requests, six separate journeys in their stated scope. Swapping scope changes acceptance for nine clauses: all eight return-departure bounds plus `pilot-17`'s transfer limit. Scope errors can therefore be exposed even when the correct-scope clause itself is vacuous. |
| Timing/service day | All 40 timing clauses in feasible requests have an exact-boundary example; 43 of 50 total timing clauses separate journeys. The one Monday morning is supported by six active service IDs and no date exception that day. The full feed has 190 active trips with beyond-midnight calls, but the pilot has no midnight, DST, weekend, or exception-day coverage. |
| Excluded features | Different-stop walking/platform equivalence, guaranteed/in-seat transfers, activity dwell, capacity and accessibility guarantees remain out of scope. No original request requires them under the explicit task conventions. |

These findings add coverage detail to the prior mechanism audit. Its already completed
uncapping diagnostic expanded 4,366 to 77,871 journey memberships without adding any
candidate classes or witness partitions; that analysis is reused, not repeated here.
Larger pools alone are not an evidenced remedy. Adding modes or new topologies might
improve a benchmark, but **is not evidence of a consequence-selector advantage**.

## Material-defect decision and project disposition

| Question | Finding |
|---|---|
| Valid test within declared scope? | Yes: a small paired development test of the implemented finite-pool methods, with provisional constructed annotations. No reference, calendar, endpoint or saved-journey defect was identified. It is not population-level validation. |
| Annotation errors distorted the comparison? | None found; all 432 rescored categories agree. Human auditing is absent, so this is qualified consistency evidence. |
| Did the universe remove necessary conditions? | It removes meaningful mode and visit-order variation and all two-transfer journeys. It does not remove the mathematical opportunity for weighting to matter: four bundles had nonuniform weights and two sequences differed. Time and scope already supply real distinctions. |
| Is another experiment warranted? | **No retest is justified by this audit.** The documented narrowness limits generalization; it is not a discovered defect invalidating the paired result or a reason to keep expanding until a win appears. |
| Original contribution | The claim that consequence weighting improves outcomes over balanced selection is **unsupported by the existing evidence**. There is no observed correctness advantage with either ordinary or oracle judgments. This does not prove universal equivalence or rule out effects in other settings. |

**Further inference for the original weighting method is paused.** This closes the
CPU coverage gate recommended by the preceding diagnosis. The audit found limitations
worth documenting, but no concrete material correction that meets the threshold for
another method experiment. Theoretical opportunity alone is insufficient.

- **Infrastructure:** retain the typed constraints, GTFS handling, solver, independent
  evaluator, paired runner, replay, budgets and audit records as reusable work within
  their supported scope. Correct operation is separate from a method contribution.
- **Generic validation:** the observed net improvement is two of 48 requests
  (+4.17 percentage points), with one damaged correct result. This small exploratory
  result supports further interest in validation generally, not superiority of E.
- **Time normalization:** deterministic literal conversion remains an engineering
  baseline. The previous source-only sensitivity is posthoc; no normalization method
  was implemented or evaluated anew in this audit. It is not a novelty claim.
- **Publication:** the current pilot does not support a positive publishable claim of
  selection-method improvement. Negative findings and reproducible infrastructure
  can be documented accurately without presenting a demonstrated new advantage.

If this infrastructure is later reused for an **independently motivated broader
benchmark**, one objective inclusion rule is: before authoring requests or producing
model outputs, fill fixed equal feature-family quotas from OD groups in stable ID
order whose public paths demonstrate the designated feature choice (bus/non-bus
alternatives, zero/one transfer, both orders of the same intermediate stops, or
independently varying outbound/return times). Use the retained feed's actual routes
and explicit supported connections; exclude inspected pilot and Stage 1 base groups.
Freeze a common public pool before reference construction. If a quota cannot be met
under exact-stop connections, record that fact rather than inventing a walking link.
The published bus and type-0 services above are the first available data to inspect;
no new feed is currently needed merely to establish their existence. This is a
**dataset specification only**, not a retest proposal, authorization, or forecast of
E wins. No expanded benchmark was built in this task.

## Artifacts and reproduction

[closeout-v1](../artifacts/stage2/closeout-v1/summary.json) contains the 48-row audit,
empty correction manifest, per-clause effects and redundancy, source/segment
coverage, 432 rescored outcomes, input hashes, and unchanged ledger hashes. Full raw
schedules and model outputs remain in their established storage; none was rewritten.
New compact audit records are committed with this report.

```bash
uv run --frozen python scripts/stage2_closeout_audit.py \
  --feed data/raw/trimet-82e6b822de008367b3d3d35bb52545807ea41b6f56623a9aa4b1162b3d54671b.zip \
  --output artifacts/stage2/closeout-v1
uv run --frozen python scripts/stage2_closeout_report.py \
  --analysis artifacts/stage2/closeout-v1 \
  --report reports/STAGE2_ANNOTATION_COVERAGE_AUDIT.md
uv run --frozen --extra dev ruff check \
  scripts/stage2_closeout_audit.py scripts/stage2_closeout_report.py
```

The report renderer uses committed compact records only. The audit additionally
requires the retained frozen feed and original saved pools/outputs. Immutable writes
reject changed records under the same identity. Focused consistency assertions and
rescoring passed; Ruff passed. No runtime correction required new regression tests,
and no unrelated test suite or GPU experiment was repeated. Historical Stage 2 usage
remains 358 generations / 681.62 measured GPU seconds (+≤30 s); cumulative usage
remains 404 / 919.01 seconds (+≤60 s). **This task adds zero.**
