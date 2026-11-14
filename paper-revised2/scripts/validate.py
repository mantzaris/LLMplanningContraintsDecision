"""Validate the minimal revision and measure changes against the submission."""
from pathlib import Path
from difflib import SequenceMatcher
import hashlib
import json
import re
import shutil
import subprocess
import tempfile

PAPER = Path(__file__).resolve().parents[1]
ORIGINAL = PAPER.parent / 'paper' / 'icaart_position'
FIRST = PAPER.parent / 'paper-revised'


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


def body_tokens(source):
    body = source[source.index('\\section'):source.index('\\begin{thebibliography}')]
    return re.findall(r'\w+|[^\w\s]', body)


def changes(original, revised):
    a, b = body_tokens(original), body_tokens(revised)
    matching = sum(x.size for x in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return {'original_tokens': len(a), 'revised_tokens': len(b),
            'retained_original_tokens': matching, 'deleted_or_replaced_tokens': len(a)-matching,
            'added_tokens': len(b)-matching,
            'original_body_retained_percent': round(100*matching/len(a), 2)}


def main():
    old = (ORIGINAL / 'main.tex').read_text()
    new = (PAPER / 'main.tex').read_text()
    for command in ('title', 'abstract'):
        pattern = r'^\\' + command + r'\{.*$'
        assert re.search(pattern, old, re.M)[0] == re.search(pattern, new, re.M)[0]
    dependencies = ['article.cls', 'SCITEPRESS.sty', 'apalike.sty', 'apalike.bst']
    for name in dependencies:
        assert (ORIGINAL / name).read_bytes() == (PAPER / name).read_bytes()
    figures = list((ORIGINAL / 'figures').glob('*.pdf'))
    for source in figures:
        assert source.read_bytes() == (PAPER / 'figures' / source.name).read_bytes()
    assert re.findall(r'\\includegraphics.*',old) == re.findall(r'\\includegraphics.*',new)
    results = {name: inspect(PAPER, name) for name in
               ('main', 'diff', 'response-to-reviewers', 'reproducibility')}
    assert results['main']['pages'] == 9
    assert 8000 <= results['main']['characters_excluding_whitespace'] <= 40000
    text = run('pdftotext', str(PAPER / 'main.pdf'), '-')
    for name in ('Alexander V. Mantzaris', 'James H. Korris',
                 'alexander.mantzaris@ucf.edu', 'james.korris@cretecinc.com'):
        assert name in text
    with tempfile.TemporaryDirectory(prefix='icaart-v2-isolated-') as tmp:
        isolated = Path(tmp)
        for name in ['main.tex'] + dependencies:
            shutil.copyfile(PAPER / name, isolated / name)
        shutil.copytree(PAPER / 'figures', isolated / 'figures')
        run('latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error', 'main.tex', cwd=isolated)
        assert inspect(isolated, 'main')['pages'] == 9
    first = changes(old, (FIRST / 'main.tex').read_text())
    second = changes(old, new)
    first_changed = first['deleted_or_replaced_tokens'] + first['added_tokens']
    second_changed = second['deleted_or_replaced_tokens'] + second['added_tokens']
    comparison = {'method': r'LaTeX body from first section to bibliography, tokens \w+|[^\w\s]; SequenceMatcher(autojunk=False). Excludes title, abstract, author block, bibliography. Source-token metric, not a semantic similarity score.',
                  'paper-revised': first, 'paper-revised2': second,
                  'reduction_in_changed_tokens_percent': round(100*(1-second_changed/first_changed),2)}
    (PAPER / 'analysis' / 'change-comparison.json').write_text(json.dumps(comparison, indent=2)+'\n')
    results.update(title_unchanged=True, abstract_unchanged=True, original_figures_unchanged=len(figures),
                   figure_inclusion_sizes_unchanged=True, template_dependencies_unchanged=True,
                   isolated_main_build=True, new_experimental_inference=0,
                   human_reference_adjudication=False,
                   page_limit_note='9 pages. Official normal short-paper allowance is 8; extra pages require the conference extra-page allowance and fee. No fee or submission action was taken.')
    (PAPER / 'analysis' / 'build-validation.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps({'builds':results,'comparison':comparison},indent=2))


if __name__ == '__main__':
    main()
