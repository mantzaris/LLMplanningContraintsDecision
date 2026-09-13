"""Build and inspect manuscript metadata/limits, including an isolated TeX build."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from plancheck.util import file_hash

PAPER = Path(__file__).resolve().parents[1]
ROOT = PAPER.parents[1]


def run(command, cwd=None):
    return subprocess.check_output(command, cwd=cwd, text=True, stderr=subprocess.STDOUT)


def inspect(directory):
    info = run(["pdfinfo", str(directory / "main.pdf")])
    text = run(["pdftotext", "-layout", str(directory / "main.pdf"), "-"])
    log = (directory / "main.log").read_text()
    assert re.search(r"^Pages:\s+8$", info, re.M)
    assert not re.search(r"Overfull|undefined|There were undefined|Rerun to get", log)
    assert re.search(r"^Author:\s*$", info, re.M)
    assert not re.search(r"mantzaris|/home/|LLMplanningContraintsDecision|github\.com", text, re.I)
    count = sum(not c.isspace() for c in text)
    assert 8000 <= count <= 40000
    return {
        "pages": 8,
        "characters_excluding_unicode_whitespace": count,
        "word_count_from_pdf": len(text.split()),
        "pdfinfo": info,
        "overfull_boxes": 0,
        "unresolved_references": 0,
        "author_metadata_empty": True,
    }


def main():
    env = dict(os.environ)
    env.pop("TEXINPUTS", None)
    env.pop("TEXMFOUTPUT", None)
    command = ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "main.tex"]
    subprocess.run(
        command, cwd=PAPER, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    source = (PAPER / "main.tex").read_text()
    assert not re.search(r"\\(?:input|include|bibliography)\s*\{", source)
    assert "\\begin{thebibliography}" in source
    abstract = source.split("\\abstract{", 1)[1].split("}\n\\onecolumn", 1)[0]
    assert 70 <= len(abstract.split()) <= 200
    provenance = json.loads((PAPER / "template/provenance.json").read_text())
    for name, checksum in provenance["files"].items():
        assert file_hash(PAPER / name) == checksum
    result = inspect(PAPER)
    with tempfile.TemporaryDirectory(prefix="icaart-isolated-") as temporary:
        isolated = Path(temporary)
        for name in ["main.tex", *provenance["files"]]:
            shutil.copyfile(PAPER / name, isolated / name)
        (isolated / "figures").mkdir()
        for path in (PAPER / "figures").glob("*.pdf"):
            shutil.copyfile(path, isolated / "figures" / path.name)
        subprocess.run(
            command,
            cwd=isolated,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        independent = inspect(isolated)
        assert (
            independent["characters_excluding_unicode_whitespace"]
            == result["characters_excluding_unicode_whitespace"]
        )
    ledger = json.loads((PAPER / "analysis/verified-storage.json").read_text())["ledgers"]
    assert all(file_hash(ROOT / path) == checksum for path, checksum in ledger.items())
    result.update(
        isolated_build_passed=True,
        abstract_words=len(abstract.split()),
        character_count_method="pdftotext -layout over complete compiled PDF, including references, captions and vector-figure text; count every non-Unicode-whitespace character. Line-break hyphens remain counted.",
        template_dependencies_unmodified=True,
        historical_ledgers_unchanged=True,
        new_experimental_calls=0,
        new_gpu_seconds=0,
        main_tex_sha256=file_hash(PAPER / "main.tex"),
        main_pdf_sha256=file_hash(PAPER / "main.pdf"),
        fonts=run(["pdffonts", str(PAPER / "main.pdf")]),
    )
    (PAPER / "analysis/build-validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        {
            k: v
            for k, v in result.items()
            if k
            in [
                "pages",
                "characters_excluding_unicode_whitespace",
                "abstract_words",
                "isolated_build_passed",
                "historical_ledgers_unchanged",
            ]
        }
    )


if __name__ == "__main__":
    main()
