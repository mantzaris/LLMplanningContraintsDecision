ICAART 2027 paper 128 — revised package

main.pdf                      Camera-ready manuscript, 8 pages.
diff.pdf                      Changes against paper/icaart_position/main.tex.
response-to-reviewers.pdf     Point-by-point response, 2 pages.
reproducibility.pdf           Exact schema, prompts, rules and source map, 9 pages.

The title and abstract are unchanged. Authors and affiliations use the supplied
camera-ready details. Original code, paper, references and numerical evidence
are unchanged. Revisions explain the existing methods and results; no new model
inference or human reference adjudication was performed. References therefore
remain provisional, and disputed judgments are described conditionally.

Diff legend: blue underlined text is added; red struck-through text is deleted.
Revised figures have blue frames; original figures appear smaller with red
crosses. Figure changes clarify labels, qualify reference-based claims and
reduce empty space; plotted input values are unchanged. The diff is for inspection,
not submission. Its pagination differs from the camera-ready manuscript.

Build all PDFs from the repository root (Python 3 and TeX Live with latexmk,
latexdiff, algorithm2e, KOMA-Script, fvextra and xurl):
  python3 paper-revised/scripts/build.py

Validate builds, unchanged title/abstract/template/data, font embedding and
an isolated manuscript compilation:
  python3 paper-revised/scripts/validate.py

Figures can be regenerated with the repository's Python 3.11 analysis environment:
  MPLCONFIGDIR=/tmp/icaart-mpl .venv/bin/python paper-revised/scripts/figures.py
Exact prompt extracts and the parser-checked example:
  .venv/bin/python paper-revised/reproducibility/export.py

The current checkout's .venv interpreter symlink was already broken. Verification
used a temporary Python 3.11 interpreter with the existing locked dependencies;
the original environment was not changed. The four original paper-analysis tests
passed. See analysis/build-validation.json and reproducibility/manifest.json.

The companion is a separate artifact, not extra proceedings pages. Keep it with
the paper's source/reproduction package; the manuscript itself is self-contained
for the definitions, algorithm, scores, study rules and limitations. Full raw
model-call logs and the frozen feed are not publicly distributed in the repository;
complete historical replay still requires those preserved files.

Official short-paper limit and added reference checked 14 November 2026:
  https://icaart.scitevents.org/Guidelines.aspx
  https://aclanthology.org/2025.findings-acl.1291/
No submission or external publication was made by this revision task.
