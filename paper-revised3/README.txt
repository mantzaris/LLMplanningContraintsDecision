ICAART 2027, paper 128: third revision

main.pdf is the eight-page paper, including references and the supplied author
names, affiliations, and email addresses. The edits address the reviewer
requests. Repeated explanations were shortened to make room for the additions.
The title, abstract, original AI Assistance Disclosure, numerical results,
figure files and sizes, and conference template are unchanged.

Files to inspect:
  main.pdf                  Revised paper: 8 pages.
  diff.pdf                  Changes against the original submission in paper/;
                            blue additions and red struck-through deletions.
                            The markup makes this inspection copy longer.
  response-to-reviewers.pdf  Item-by-item response: 2 pages.
  reproducibility.pdf       Exact prompts, language schema, and protocol details
                            requested by the reviewer: a separate companion,
                            not pages appended to the proceedings paper.

The corresponding .tex files and original template dependencies are included.
No new model runs or human adjudication were performed. The paper explicitly
describes the references as provisional and limits its diagnostic claims
accordingly. The companion explains which evidence is public and which full
historical files are needed for replay.

From the repository root, rebuild and check with:
  python3 paper-revised3/scripts/build.py
  python3 paper-revised3/scripts/validate.py

The build requires latexmk, pdflatex, and latexdiff. Validation also uses
pdfinfo, pdftotext, and pdffonts. It checks the eight-page limit, preserved
material, embedded fonts, LaTeX diagnostics, and a separate clean build.
Results are saved in analysis/build-validation.json.
