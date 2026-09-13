# ICAART 2027 position-paper package

The anonymous [eight-page PDF](main.pdf), **“Linking Candidate Coverage to Decision Quality: A Framework for LLM Planning Evaluation,”** proposes a structured framework connecting benchmark coverage, candidate availability, validation behavior, final decisions, and inference cost. Two exploratory transit studies illustrate what its reproducible analyses reveal beyond aggregate accuracy. Experimental values and corrected interpretations are preserved, including the unfavorable weighting and solver-guided sampling comparisons. This is a prepared draft, **not a conference submission**. See [AUTHOR_HANDOFF.md](AUTHOR_HANDOFF.md) before any submission or artifact release.

All prose and the bibliography are in [main.tex](main.tex). The four files `article.cls`, `SCITEPRESS.sty`, `apalike.sty`, and `apalike.bst` are byte-identical official template dependencies. Standard TeX Live packages are required; `algorithm2e` is required by the official style even though this paper contains no algorithm float. [Template provenance](template/provenance.json) records the download and checksums.

## Build from the committed files

From the repository root:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error -cd paper/icaart_position/main.tex
```

No bibliography file, section inputs, data feed, model, GPU, or network connection is required. PDF figures and the complete manuscript are committed. The build was verified with pdfTeX 1.40.20 / TeX Live 2019 and latexmk, using the downloaded official SCITEPRESS class/style. No template formatting was changed.

## Reproduce the offline analysis and figures

Use the repository's locked Python 3.11 environment:

```bash
uv sync --frozen --extra dev --extra analysis
.venv/bin/python paper/icaart_position/scripts/analyze.py
MPLCONFIGDIR=/tmp/icaart-mpl .venv/bin/python paper/icaart_position/scripts/figures.py
.venv/bin/pytest -q paper/icaart_position/scripts/test_analysis.py
.venv/bin/python paper/icaart_position/scripts/validate.py
```

`analyze.py` reads the original local `runs/stage2-pilot-v1` and `runs/stage3-fresh` and provisional references. It checks 152 Stage 2 and 1,225 Stage 3 raw-file hashes, the three Stage 3 archive hashes, and frozen protocols. It reconstructs request-level results using the existing independent checker, verifies Stage 2 witness rankings, and reproduces all 288 saved Stage 3 oracle-prefix outputs. It never loads a model. The official source modules, protocols, and historical reports remain unchanged.

Raw inputs are already preserved in the project's established storage, detailed in [verified-storage.json](analysis/verified-storage.json) and [the original Stage 3 storage record](../../artifacts/stage3/pilot-v1/storage.json). The complete Stage 3 archive has SHA-256 `859bb53e3070243ac7c41308d4c2056233f312caf48c5c4bd8145ea6fe32794d`. They were all present locally and checksum-verified for this task; no remote access was necessary. The stored remote replication statements are historical records, not a new remote availability check. Use the existing authorized shell/stdin transfer workflow if local archives are absent; connection credentials are intentionally not embedded here. Verify hashes before extraction. Do not substitute a newly downloaded feed for the frozen source.

To redraw figures from committed derived tables only, run `figures.py`; raw artifacts are unnecessary. Its [manifest](figure-provenance.json) records input and figure hashes and the illustrative-case rule. Compact traces contain selected journey endpoints, not the full feed or full prompts.

For a complete ordinary Stage 3 CPU replay, choose a new ignored output directory:

```bash
.venv/bin/python -m plancheck.sampling_run --config configs/sampling.json \
  --public data/prepared/stage3/public --run runs/icaart-stage3-replay \
  --replay-from runs/stage3-fresh
.venv/bin/python paper/icaart_position/scripts/verify_replay.py
```

If prepared public inputs are absent, restore `public-scenarios.json` as `scenarios.json`, and its `pools/` alongside it, from the preserved run, as described in the historical report. Replay loads cached responses only. All 32 decisions, formulas, witnesses, judgments, and logical costs match; 19 original first-use judge calls become cache hits, so nine pair files differ solely in cache-provenance flags. Do not interpret those cache hits as new inference or recompute historical actual cost from replay.

## Outputs and checks

- `analysis/stage2-requests.csv`: 48 bases × two selectors × four budgets, including outcome categories and stopping reasons.
- `analysis/stage3-requests.csv`: 32 bases × three sampling arms × three checkpoints, including joint G/S, oracle-witness correctness, and existence of a correct candidate-selected output.
- `analysis/stage3-joint.csv`, `stage3-paired.csv`: all checkpoints, including direct independent/diversified pairing.
- `analysis/selection-failures.json`: every matching-candidate-but-incorrect outcome, with actual elimination steps.
- `analysis/worked-examples.json`: two illustrative cases behind the transit figure.
- `analysis/annotation-review.csv`: 80 provisional references with blank human-review decisions.
- `analysis/input-manifest.json`, `costs.json`: provenance and event-derived accounting.
- `analysis/build-validation.json`: character count, anonymous metadata, unchanged official dependencies, and isolated-build validation.

The manuscript uses “Study 1” for Stage 2 and “Study 2” for Stage 3. A/B/C remain only in analysis files as independent/diversified/solver-guided sampling; D/E remain balanced/consequence-weighted selection in Stage 2 files. Studies are never pooled.

To render every page for inspection:

```bash
mkdir -p /tmp/icaart-pages
pdftoppm -r 115 -png paper/icaart_position/main.pdf /tmp/icaart-pages/page
pdfinfo paper/icaart_position/main.pdf
pdftotext -layout paper/icaart_position/main.pdf /tmp/icaart-text.txt
```

No new experimental model calls or GPU work were performed for this package. Historical ledgers retain their original hashes.
