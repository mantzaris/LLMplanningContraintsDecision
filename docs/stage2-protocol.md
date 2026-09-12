# Controlled feasibility pilot, frozen v1

This is an exploratory development pilot of the unchanged Stage 1 weighted-pair
selection rule. It is not the final publication evaluation. The machine-readable
[protocol](../data/pilot/protocol.json), [config](../configs/pilot.json), requests,
reference annotations and automated review are committed before any fresh pilot
judgment or evaluation. The starting audit is in
[STAGE2_STARTING_STATE.md](../reports/STAGE2_STARTING_STATE.md).

The data acquisition, feed checksum, service date, spatial bounds, route selection,
transfer exclusions, objective, and deterministic candidate-pool caps are unchanged.
Forty-eight new OD pairs are chosen before model outcomes: cycle the three selected
routes, prefer less-reused endpoints, then greater scheduled coverage and stable IDs.
Exclude every previously selected segment OD pair and its reverse, including held-out
pairs. Each route supplies 16 pairs. Six requirement families supply eight requests
each: inclusive timing, transfers, mode exclusion/latest departure, directional scope,
ordered intermediate calls, and infeasibility. A deterministic middle journey in the
public objective order supplies construction times and intermediate calls. It never
prunes the pool or enters inference as an answer. There are 40 feasible and eight
infeasible references in the declared pools. All requests are assistant-authored
research constructions over published schedules, not observed passenger requests.

The separate wording reviewer parses requirement clauses into reference dictionaries
without importing the constructor or prediction compiler, and checks exact agreement.
It also evaluates feasibility with the independent reference checker. All annotations
remain provisional, automatically checked, and not human audited. CSV review fields
are left blank for future human review. Constructing both wording and references with
software remains a source of correlated error even with this second implementation.
The return segment has explicit endpoints; intervening movement is outside the task.
Intermediate calls count while remaining aboard; dwell/activity visits are unsupported.

D and E receive exactly the same four sampled translations and the same saved,
syntactically and semantically deduplicated bundle. A semantic class is an exact
acceptance vector over the completed public pool. Translation is Qwen2.5-7B-Instruct
at the verified revision, temperature 0.7, top-p 0.95, inherited top-k 20 and repetition
penalty 1.05, maximum 768 new tokens. Judgments and secondary repairs are greedy.
Seeds start at 21000 plus candidate index; generation replicate 1 adds 100000.
Journey judgment seeds depend on replicate seed and public journey ID, never selector.
Fresh prompts contain the original request and deterministic journey rendering, without
formulas, votes, reference labels or the selector's preference. Both roles use the same
model, which is not an independent oracle.

For pair (i,j), `I_ij` is the count of available selected plans rejected by the other
interpretation. D scores each witness by separated pair count; E sums `1 + I_ij` over
those pairs. Unit cost means one judgment. Tokens are measured separately: equal
judgment counts are not equal token costs. Exact rational scores break ties by journey
ID. Missing plans contribute zero impact, without deleting the interpretation. Solver
timeouts remain timeouts. If no witness exists after complete finite evaluation, the
remaining candidates are equivalent on that domain. This is not proof of correct
natural-language interpretation.

Each selector follows one trajectory of at most four judgments. Prefixes supply budgets
0, 1, 2, and 4 with no repeated GPU work. Definite labels eliminate disagreeing classes;
uncertain judgments eliminate none. Stop on no witness, candidate exhaustion, or budget.
The output is the first surviving class in generation order; exhaustion yields an
unresolved output with its initial plan retained only for diagnostics. **D/E model repair
is disabled in this pilot**, a predeclared change in repair allowance from Stage 1 to
isolate selection. The selection score is unchanged. A uses the first translation;
B performs one ordinary critique per replicate; C uses two concrete positive/negative
examples and at most one repair on replicate 0. These remain task-specific adaptations,
not exact reproductions of predecessor experiments.

The oracle diagnostic runs offline with exact independent reference labels and the same
D/E elimination policy. It makes no repair/model calls and is never included in ordinary
model-judged performance. Reference-equivalent candidate coverage, judgment errors and
selection divergence are diagnostic annotations added only after inference.

The planned scope is 48 bases × two generation replicates. The worst-case count before
cache savings is 1,392 generations: 384 shared translations, 768 D/E judgments, 96 B
critiques, and at most 144 C judgments/repairs. A and secondary first translations share
valid cache entries. Every method is still logically charged its own calls and tokens.
A separate append-only Stage 2 ledger has a 1,500-attempt ceiling. The model-resident
guard is 7,170 seconds, reserving 30 seconds below the two-hour authorization for disposal
and watchdog uncertainty. No training, tuning or further automatic stage is authorized.

The first four bases' 16 translations form an included timing diagnostic. Before any
judging, use its p95 generation time or the Stage 1 p95 (whichever is larger), multiplied
by 1.5, plus 120 seconds and two seconds per base/replicate, to forecast the full upper
call count. If it does not fit, reduce two replicates to one, then remove six-base blocks
from the end of the frozen order. No comparative outcomes are inspected for this choice.
Reserve a complete pair's calls/time before starting it; retain any unexpected incomplete
attempts. Successful calls and completed pairs resume without regeneration. Crashed
sessions conservatively consume their entire remaining allocation.

Primary outcome: a valid feasible plan or a correct infeasibility conclusion within the
pool. Keep incorrect plans, false infeasibility, unresolved outputs, invalid model
outputs, solver timeouts and infrastructure failures distinct. Retain the semantic
verification flag separately. Report feasible and infeasible requests separately,
validation/repair improvement and damage, calls/tokens/latency/solver time, actual GPU
use and independently attributed logical cost. Analyze the full predeclared sample;
report incomplete coverage explicitly. The divergent-trajectory subset is conditional
and cannot replace that result. Estimate paired E−D differences and uncertainty by
resampling base-request groups, with replicates together (10,000 draws, seed 2201).
Do not interpret this small exploratory pilot as a confirmatory significance test.
Distinct ODs still share routes, dates, stops and wording templates, limiting external
validity and the interpretation of independent base sampling.

Representatives are selected without discretion: first lexicographic tie, failure,
correct case and divergent trajectory, allowing overlap. Plots use saved artifacts only.
If the pod is unreachable, finish CPU diagnostics, preserve a blocked-execution record,
and leave the fresh sample unrun. Old smoke reanalysis must be labeled separately and
must not be presented as the requested pilot's performance.
