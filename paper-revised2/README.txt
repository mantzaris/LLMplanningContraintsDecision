ICAART 2027 paper 128 — second, minimal revision

main.pdf                      Revised manuscript (9 pages).
diff.pdf                      Marked changes against the original submission (10 pages).
response-to-reviewers.pdf      Updated point-by-point response (2 pages).
reproducibility.pdf            Exact implementation details (9-page companion).
main.tex and companion .tex    Editable sources.

This version starts from paper/icaart_position/main.tex, not the first revision.
It preserves the original introduction, related-work paragraphs, results,
discussion and conclusion structure. All four original figure PDFs and their
inclusion sizes are unchanged. The title and abstract are unchanged verbatim;
authors and affiliations retain the supplied camera-ready details. The original
submission is untouched.

Changes focus on the reviewers' requests: definitions, compact pseudocode,
pre-validation candidate coverage, explicit witness scores and cost, reference
provenance and conditional attribution, reproducibility pointers, and specific
English errors. The unused probability equation is removed. Long prompt/schema
and protocol details remain in the companion. There is no new experimental
inference, changed numerical evidence, or invented human reference adjudication.

Change size (excluding title, abstract, author block and bibliography):
The first revision retains 62.83% of original body source tokens; this version
retains about 95%. It has about 64% fewer added/deleted/replaced source tokens.
Exact counts and the comparison method are in analysis/change-comparison.json.
This is a lexical LaTeX-source comparison, not a semantic similarity score.

Page-count tradeoff:
Preserving the original material while adding the required explanations yields
nine proceedings pages. The normal ICAART short-paper allowance is eight; use
of this nine-page version requires the extra-page allowance and associated fee.
No registration, payment, submission or publication has been made.
Official rule, checked in this revision session:
https://icaart.scitevents.org/Guidelines.aspx

Diff legend:
Blue underlined text is added; red struck-through text is deleted. Unchanged
figures are shown normally. The diff is an inspection artifact, not for submission.

Build from the repository root (Python 3, TeX Live, latexmk, latexdiff):
  python3 paper-revised2/scripts/build.py
Validate PDFs, unchanged figures/template/title/abstract, and isolated build:
  python3 paper-revised2/scripts/validate.py

All four PDFs compile without overfull boxes or unresolved references, and all
fonts are embedded. Main and diff pages were rendered for visual inspection.
See analysis/build-validation.json. Long-form reproduction details and source
availability limits are in reproducibility.pdf. The full frozen feed and raw
model-call logs remain outside the public repository.
