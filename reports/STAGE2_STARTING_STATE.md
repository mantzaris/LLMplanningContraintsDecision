# Stage 2 starting-state audit

Starting revision: `ab3e17eaaa14ac9bdc4fa54b59c7ecfb29feaca0` on `main`.
The working tree was clean; origin pointed to the requested GitHub repository.
No applicable `AGENTS.md` was present at the repository or parent locations.
The README, methodology, literature, data/running documentation, Stage 1 report,
configuration files, provenance manifests, model metadata, GPU ledger, recent commits,
and implementation were inspected. No equivalent controlled pilot was present.

Stage 1 is executable, with a typed Python package, GTFS acquisition/preparation,
finite Z3 planner, separately implemented reference evaluator, A–E methods, fresh
model judgments, bounded repair, append-only model journals, and original-revision
replay. Its 24 existing tests passed at the start. Full public pools, independent
reference files and original GPU outputs are retained locally; summaries and hashes
are committed. Sixty requests exist across six OD groups, five requirement variants,
and two minimal paraphrases. The publication holdout was not run.

The frozen TriMet feed has SHA-256
`82e6b822de008367b3d3d35bb52545807ea41b6f56623a9aa4b1162b3d54671b`.
The coverage-selected network has routes 2, 4 and 17, all buses, 70 stops and 6,574
ride edges on 2026-09-14, 07:00–10:00 America/Los_Angeles. Pools are deterministically
capped at 64 journeys per segment and 256 combined journeys. Claims remain
conditional on those pools. The small bus-only network limits mode diversity.

Actual verified model: Qwen/Qwen2.5-7B-Instruct, revision
`a09a35458c702b33eeacc393d103063234e8bc28`, BF16, Transformers 4.51.3,
PyTorch 2.8.0+cu128, RTX PRO 6000 Blackwell. Translation and judgment used the same
model. Three preserved smoke identities record the original malformed schema
responses, schema-prompt clarification, and fenced-JSON parser repair. Total actual
Stage 1 use was 46 generations and 237.390215 model-resident GPU seconds, plus a
conservative 30-second uncertainty allowance. No project model process remained at
Stage 1 completion. Stage 2 must not reset this ledger.

The latest smoke used four related requests from one base OD group. The three
requests with valid translations each collapsed from four predictions to one
semantic class; the fourth had no valid predictions. Thus the natural D/E comparison
never reached a distinguishing witness. Two outputs satisfied the provisional
reference, one reported false infeasibility after converting 09:15 to 54,900 seconds,
and one declined a supported but contradictory timing request as unsupported.
The timing case also converted 08:15 to 29,400 seconds; it happened to be equivalent
on the checked pool. Extra validation did not demonstrate an advantage. Five parsed
C judgments matched provisional labels, while some explanations contained errors.
These observations cannot establish general judge reliability or selector benefit.

Necessary Stage 2 changes: shared saved candidate bundles and validation prefixes,
an explicit second-stage budget allocation, fresh coverage sampling, an independently
implemented narrow wording review, exclusive evaluation categories, paired/base-level
analysis, a separate oracle replay, and descriptive selector diagnostics. Historical
results and source revisions remain intact. The old `unresolved` metric measured lack
of semantic confirmation and overlapped valid returned plans; Stage 2 instead reports
exclusive outcome categories and retains that confirmation flag separately. This is
an evaluation-definition clarification, not an invalidation of the old raw outputs.
