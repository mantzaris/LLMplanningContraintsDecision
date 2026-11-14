"""Build the minimal revision and its diff against the original submission."""
from pathlib import Path
import subprocess

PAPER = Path(__file__).resolve().parents[1]
ORIGINAL = PAPER.parent / 'paper' / 'icaart_position'


def build(name):
    result = subprocess.run(['latexmk', '-pdf', '-interaction=nonstopmode',
        '-halt-on-error', name + '.tex'], cwd=PAPER, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(result.stdout)
    print(name + '.pdf built')


def main():
    build('main')
    # All four figure assets and inclusion sizes are unchanged: no figure markup.
    diff = subprocess.check_output(['latexdiff', '--graphics-markup=none',
        '--math-markup=whole', '--disable-citation-markup',
        '--label=Original submission', '--label=Minimal revision',
        str(ORIGINAL / 'main.tex'), str(PAPER / 'main.tex')], text=True)
    (PAPER / 'diff.tex').write_text(diff)
    build('diff')
    for name in ('reproducibility', 'response-to-reviewers'):
        if (PAPER / (name + '.tex')).exists():
            build(name)


if __name__ == '__main__':
    main()
