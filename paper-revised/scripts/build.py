"""Build the revised paper, review diff, and companions without model inference."""
from pathlib import Path
import subprocess
import tempfile
import shutil

PAPER = Path(__file__).resolve().parents[1]
ORIGINAL = PAPER.parent / 'paper' / 'icaart_position'


def build(name):
    result = subprocess.run(
        ['latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error', name + '.tex'],
        cwd=PAPER, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(result.stdout)
    print(name + '.pdf built')


def main():
    build('main')
    old_figures = PAPER / 'diff-original-figures'
    old_figures.mkdir(exist_ok=True)
    for path in (ORIGINAL / 'figures').glob('*.pdf'):
        shutil.copyfile(path, old_figures / path.name)
    # Rebase only old figure paths, so latexdiff also displays changed labels/layout.
    old_source = (ORIGINAL / 'main.tex').read_text().replace('{figures/', '{diff-original-figures/')
    with tempfile.TemporaryDirectory(prefix='icaart-diff-') as temp:
        old = Path(temp) / 'submitted.tex'
        old.write_text(old_source)
        diff = subprocess.check_output([
            'latexdiff', '--graphics-markup=both', '--math-markup=whole',
            '--append-textcmd=KwIn', '--disable-citation-markup',
            '--label=Submitted manuscript', '--label=Camera-ready revision',
            str(old), str(PAPER / 'main.tex')], text=True)
    # Allow space for latexdiff's blue figure frames, only in the inspection PDF.
    for width in ('textwidth', 'columnwidth'):
        diff = diff.replace('width=\\' + width + ']',
                            'width=\\dimexpr\\' + width + '-7pt\\relax]')
    (PAPER / 'diff.tex').write_text(diff)
    build('diff')
    for name in ('reproducibility', 'response-to-reviewers'):
        if (PAPER / (name + '.tex')).exists():
            build(name)


if __name__ == '__main__':
    main()
