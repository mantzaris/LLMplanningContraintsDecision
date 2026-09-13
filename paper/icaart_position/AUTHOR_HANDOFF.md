# Author handoff — ICAART 2027 position-paper draft

**Complete anonymous draft; not submitted.** **“Linking Candidate Coverage to Decision Quality: A Framework for LLM Planning Evaluation”** proposes a structured framework connecting benchmark coverage, candidate availability, validation behavior, final decisions, and cost. Two exploratory transit studies demonstrate the additional information it provides beyond aggregate accuracy. Further experimental inference remains paused.

The editorial revision foregrounds three contributions: the linked framework, empirical demonstrations of its explanatory value, and a reproducible request-level procedure. The abstract and introduction lead with these contributions; the discussion gives concrete guidance on benchmark construction, component diagnosis, and cost reporting; the conclusion explains what future evaluations should measure. Figure titles and captions identify the questions each analysis answers. All experimental values, adverse primary comparisons, provisional annotation status, and the corrected oracle sequence below are preserved. No claim is made that using the framework itself improves accuracy or reduces cost.

## Evidence and the specific increment

Stage 2 (Study 1 in the paper) remains a 48-base selector comparison. Both selectors move from 31/48 initially to 33/48 after validation: three recoveries and one deterioration. Of 18 consequential bundles, 14 have uniform weights; two further bundles retain the same choice through tie-breaking. Only two witness sequences differ, without a correctness difference. The bus-only benchmark has 19 constant mode clauses, 6/24 varying transfer clauses, and no ordering exclusion beyond stop presence. Cap-removal results are an earlier offline audit, not a new experiment.

Stage 3 (Study 2) has 32 distinct bases under a different protocol. Final joint counts, in G1S1/G1S0/G0S1/G0S0 order, are:

| Sampling arm | Joint counts | Correctness | Oracle-witness correctness | Any candidate-selected output correct |
|---|---|---:|---:|---:|
| Independent | 27 / 0 / 1 / 4 | 28/32 | 27/32 | 28/32 |
| Diversified | 28 / 3 / 0 / 1 | 28/32 | 31/32 | 31/32 |
| Solver-guided | 25 / 0 / 0 / 7 | 25/32 | 25/32 | 25/32 |

Independent versus diversified has **one win, 30 ties, one loss**. Solver-guided has zero wins, 29 ties, three losses against each baseline. Equal baseline totals do not mean the same requests succeed. Three diversified final G1S0 cases lose their matching candidates to two false positive judgments and one false negative; a fourth such failure occurs at checkpoint four. These causes were reconstructed, not assumed from the joint cell.

Oracle replay supplies truthful labels to the **same bounded witness-selection/elimination procedure**. It is not an unconditional ceiling. In independent `sampling-20`, an incorrect first label and a correct second label select a lower-bound formalization whose departure is exactly the requested upper bound. Truthful first-witness rejection takes a different path and returns an invalid plan. Historical numbers need no correction. A separate [narrative correction](../../reports/STAGE3_ORACLE_NARRATIVE_CORRECTION.md) records that the original report incorrectly called both positive judgments erroneous; only the first was wrong. The original report remains intact. “Any candidate-selected output correct” is a separate privileged diagnostic restricted to existing candidates' deterministic outputs.

Final logical token totals are 617,643 / 626,497 / 811,760. Solver-guided overhead is **31.43% over independent and 29.57% over diversified**, denominator = the baseline's consumed input plus output for generation and final-prefix validation across 32 requests. Equal allocations did not imply equal consumption. Every trajectory reached eight attempts before exhausting its allowance.

Prior work already diagnoses components and selection bottlenecks. SSV reports verification precision/coverage; sampling-diversity work examines verifier effects; VERGE reports funnels and compute parity. Our narrower contribution links request-level availability and decisions with benchmark semantic coverage. The ARTEMIS-inspired model-judged selector is expressly an adaptation, not a human-validation reproduction.

## Annotation status and author decisions

References remain **provisional**, without independent human adjudication. The [80-request review sheet](analysis/annotation-review.csv) contains requests, reference rules, pool sizes, feasible counts, and blank reviewer decisions. Developer/automated checks are not relabeled human review. The draft is complete without inventing review or approval.

Before submission, authors should review the argument, facts, bibliography, and AI-assisted wording; decide authorship and consent; and resolve annotation concerns. This package does not assert all-author approval or completed human verification. Future reference corrections require separately identified rescoring, preserving original results. Current evidence supports a bounded position paper, not an empirical superiority claim.

## Verified conference requirements

Checked **13 September 2026** against official 2027 pages:

| Requirement | Rule and source |
|---|---|
| Position-paper length | 8,000–40,000 characters excluding whitespace, including references, tables, graphs, and appendices; normal eight proceedings pages. [Guidelines](https://icaart.scitevents.org/Guidelines.aspx) |
| Template | Eight pages here, including figures and references, with unchanged official class/style. [Templates](https://icaart.scitevents.org/Templates.aspx) |
| Submission deadline | **22 October 2026, Anywhere on Earth**. Notification 4 December; camera-ready/registration 18 December. September's regular-paper deadline is a different category. [Important dates](https://icaart.scitevents.org/ImportantDates.aspx) |
| Review | Anonymous double-blind manuscript; omit identifying details and acknowledgments. [Guidelines](https://icaart.scitevents.org/Guidelines.aspx) |
| AI assistance | Disclose tool, affected parts, and use; tools are not authors. Pages specify acknowledgments, while the AI page also permits an appropriate section. [AI tools](https://icaart.scitevents.org/AiTools.aspx) |
| Public posting | Do not publicly post the submitted manuscript during review. [Guidelines](https://icaart.scitevents.org/Guidelines.aspx) |

Characters are counted from the full PDF with `pdftotext -layout`, retaining every non-Unicode-whitespace character, including captions, references, and vector-figure labels. Printed line-break hyphens remain counted. This reproducible approximation is comfortably within range; the submission system may differ. The revised abstract is 177 whitespace-delimited words, within the official template's 70–200 recommendation. Exact checks: [build-validation.json](analysis/build-validation.json).

## Anonymity, disclosure, and artifact release

Visible author information and PDF author metadata are empty. The manuscript omits identifying repository URLs, account names, local paths, commits, and funding/affiliation acknowledgments. Case IDs appear only in the analysis mapping. **The anonymous review manuscript is `main.pdf`, not this entire repository.**

No existing submission or under-review status was found. The authorized repository update preserves public history and adds this draft; it is not conference submission. Historical reports, request text, and the manuscript title may make the work discoverable. Do not erase history to manufacture anonymity. Before submitting, confirm how the conference treats this prior availability and avoid subsequent public manuscript updates during review. No organizer message, external submission, or other publication was performed.

The anonymous **AI Assistance Disclosure** follows the conclusion, with a tool citation in the findings as well. It names OpenAI Codex and identifies prose/analysis/figure-code assistance, without an acknowledgments heading or identifying details. **Authors must confirm placement and whether the central scope statement plus affected-section citations satisfies the final declaration requirement.** The acknowledgment-placement and anonymity instructions are not fully aligned. This remains a handoff decision, not an invented declaration or reason to leave the draft unfinished.

The frozen feed and full prompts remain outside Git. Figures contain only scheduled facts needed for two illustrative cases, with the agency source cited. Full-feed redistribution has not been newly authorized through an assumed open-data license; consult [existing provenance/terms](../../docs/data.md) before releasing raw archives. Persistent pod storage is established project storage, not a permanent public artifact service. An anonymous artifact-release route and long-term archive remain author decisions.

## Reproduction and validation

[README.md](README.md) provides exact commands and restoration paths. The package contains self-contained TeX and bibliography, PDF, four unchanged official dependencies, four PDF/PNG figure groups, request-level tables, compact traces, hashes, and regeneration/check scripts. Primary-source verification is recorded in [bibliography-verification.json](bibliography-verification.json).

The offline audit verifies 152 Stage 2 files, 1,225 Stage 3 files, and all three Stage 3 archives against original checksums. All 288 oracle-prefix records reproduce after JSON normalization. Ordinary CPU replay matches every decision, formula, witness, judgment, and logical charge for 32/32 bases. Only 19 original first-use judge-call `cached` flags become true: 23/32 pair files are byte-identical. See [replay verification](analysis/replay-verification.json).

Build checks cover eight pages, limits, references, dependency hashes, and anonymous metadata. An isolated build uses only `main.tex`, official dependencies, and PDF figures. Every revised page was visually inspected; the shortened joint-figure title improves label readability. Template margins, fonts, and spacing were not changed. Four focused tests cover joint cells, direct pairing, non-ceiling oracle behavior, and actual matching-candidate elimination. Historical evidence and figure input tables remain unchanged; only presentation and its validation records were updated.

**New experimental generations: 0. New GPU seconds: 0.** Historical totals remain 1,087 generations and 2,179.6913 measured GPU seconds plus at most 120 seconds of allowances. Original ledgers are unchanged. No model service, GPU connection, training, or external model API call was used for this manuscript task.

Original package preparation started at `78a9d56f290aad83bc65ea7165ede0f01f0efa33`, clean `main`. This editorial revision started at `2f530f672ce510e82796cc3d529ac14686e36b98` and built on the existing local abstract/introduction edits and PDF. Delivery commits are in Git history and completion messages; historical results and frozen implementation were not rewritten.
