"""Check the eight-page manuscript and protected original material."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import tempfile

PAPER = Path(__file__).resolve().parents[1]
ORIGINAL = PAPER.parent / 'paper' / 'icaart_position'


def run(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True, stderr=subprocess.STDOUT)


def inspect(directory, name):
    pdf = directory / (name + '.pdf')
    info = run('pdfinfo', str(pdf))
    text = run('pdftotext', '-layout', str(pdf), '-')
    log = (directory / (name + '.log')).read_text()
    assert not re.search(r'Overfull|undefined|Rerun to get', log), name
    fonts = run('pdffonts', str(pdf)).splitlines()[2:]
    assert fonts and all(line.split()[-5] == 'yes' for line in fonts), name
    return {'pages': int(re.search(r'^Pages:\s+(\d+)', info, re.M)[1]),
            'characters_excluding_whitespace': sum(not c.isspace() for c in text),
            'all_fonts_embedded': True, 'overfull_boxes': 0, 'unresolved_references': 0,
            'sha256': hashlib.sha256(pdf.read_bytes()).hexdigest()}


def main():
    old = (ORIGINAL / 'main.tex').read_text()
    new = (PAPER / 'main.tex').read_text()
    for command in ('title', 'abstract'):
        pattern = r'^\\' + command + r'\{.*$'
        assert re.search(pattern, old, re.M)[0] == re.search(pattern, new, re.M)[0]
    disclosure = r'\\subsection\*\{AI Assistance Disclosure\}\n\\label\{sec:ai\}\n[^\n]+'
    exact_disclosure = re.search(disclosure, old)[0]
    assert re.search(disclosure, new)[0] == exact_disclosure
    assert exact_disclosure in (PAPER / 'diff.tex').read_text()
    assert 'Acknowledgements' not in new
    dependencies = ['article.cls', 'SCITEPRESS.sty', 'apalike.sty', 'apalike.bst']
    for name in dependencies:
        assert (ORIGINAL / name).read_bytes() == (PAPER / name).read_bytes()
    figures = list((ORIGINAL / 'figures').glob('*.pdf'))
    for source in figures:
        assert source.read_bytes() == (PAPER / 'figures' / source.name).read_bytes()
    assert re.findall(r'\\includegraphics.*',old) == re.findall(r'\\includegraphics.*',new)
    results = {name: inspect(PAPER, name) for name in
               ('main', 'diff', 'response-to-reviewers', 'reproducibility')}
    assert results['main']['pages'] == 8
    assert 8000 <= results['main']['characters_excluding_whitespace'] <= 40000
    text = run('pdftotext', str(PAPER / 'main.pdf'), '-')
    for name in ('Alexander V. Mantzaris', 'James H. Korris',
                 'alexander.mantzaris@ucf.edu', 'james.korris@cretecinc.com',
                 'AI Assistance Disclosure'):
        assert name in text
    # Primary reported outcomes and resource amounts remain in the main paper.
    preserved_values = ['31/48','33/48','35/48','27/32','31/32','28/32','25/32',
                        '11/19','7/31','4,366','77,871','617,643','626,497','811,760',
                        '31.43','29.57','2,081,931','1,743,059','1,207.31','53.37','681.62']
    for value in preserved_values:
        assert value in old and value in new, value
    with tempfile.TemporaryDirectory(prefix='icaart-v3-isolated-') as tmp:
        isolated = Path(tmp)
        for name in ['main.tex'] + dependencies:
            shutil.copyfile(PAPER / name, isolated / name)
        shutil.copytree(PAPER / 'figures', isolated / 'figures')
        run('latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error', 'main.tex', cwd=isolated)
        assert inspect(isolated, 'main')['pages'] == 8
    results.update(title_unchanged=True, abstract_unchanged=True,
                   ai_disclosure_unchanged=True, acknowledgements_added=False,
                   original_figures_unchanged=len(figures), figure_inclusion_sizes_unchanged=True,
                   template_dependencies_unchanged=True, isolated_main_build=True,
                   primary_result_values_present=preserved_values,
                   new_experimental_inference=0, human_reference_adjudication=False,
                   manuscript_page_limit=8)
    (PAPER / 'analysis' / 'build-validation.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
