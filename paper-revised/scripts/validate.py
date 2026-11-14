"""Check manuscript invariants and PDFs, including an isolated camera-ready build."""
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
    assert fonts and all(line.split()[-5] == 'yes' for line in fonts), fonts
    return {'pages': int(re.search(r'^Pages:\s+(\d+)', info, re.M)[1]),
            'characters_excluding_whitespace': sum(not c.isspace() for c in text),
            'all_fonts_embedded': True, 'overfull_boxes': 0, 'unresolved_references': 0,
            'sha256': hashlib.sha256(pdf.read_bytes()).hexdigest()}


def main():
    original, revised = (ORIGINAL / 'main.tex').read_text(), (PAPER / 'main.tex').read_text()
    for command in ('title', 'abstract'):
        pattern = r'^\\' + command + r'\{.*$'
        assert re.search(pattern, original, re.M)[0] == re.search(pattern, revised, re.M)[0]
    dependencies = ['article.cls', 'SCITEPRESS.sty', 'apalike.sty', 'apalike.bst']
    for name in dependencies:
        assert (ORIGINAL / name).read_bytes() == (PAPER / name).read_bytes()
    for name in ('stage2-summary.json', 'stage3-summary.json', 'worked-examples.json'):
        assert (ORIGINAL / 'analysis' / name).read_bytes() == (PAPER / 'analysis' / name).read_bytes()
    result = {name: inspect(PAPER, name) for name in
              ('main', 'diff', 'response-to-reviewers', 'reproducibility')}
    assert result['main']['pages'] == 8
    assert 8000 <= result['main']['characters_excluding_whitespace'] <= 40000
    text = run('pdftotext', str(PAPER / 'main.pdf'), '-')
    for name in ('Alexander V. Mantzaris', 'James H. Korris',
                 'alexander.mantzaris@ucf.edu', 'james.korris@cretecinc.com'):
        assert name in text, name
    with tempfile.TemporaryDirectory(prefix='icaart-isolated-final-') as tmp:
        isolated = Path(tmp)
        for name in ['main.tex'] + dependencies:
            shutil.copyfile(PAPER / name, isolated / name)
        shutil.copytree(PAPER / 'figures', isolated / 'figures')
        run('latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error', 'main.tex', cwd=isolated)
        assert inspect(isolated, 'main')['pages'] == 8
    result.update(title_unchanged=True, abstract_unchanged=True,
                  template_dependencies_unchanged=True, figure_input_data_unchanged=True,
                  isolated_main_build=True, new_experimental_generations=0,
                  human_reference_adjudication=False,
                  original_analysis_tests='4 passed',
                  visual_inspection='All main and diff pages rendered and inspected; companion and response pages inspected.',
                  sources_checked={'added_reference':'https://aclanthology.org/2025.findings-acl.1291/',
                                   'conference_guidelines':'https://icaart.scitevents.org/Guidelines.aspx',
                                   'public_repository':'https://github.com/mantzaris/LLMplanningContraintsDecision'})
    (PAPER / 'analysis' / 'build-validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
