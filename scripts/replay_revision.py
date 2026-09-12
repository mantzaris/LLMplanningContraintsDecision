#!/usr/bin/env python3
"""Replay a saved run with its original committed source, without changing main."""

from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.run / "manifest.json").read_text())
    revision = manifest["repository_revision"]
    if not re.fullmatch("[0-9a-f]{40}", revision):
        raise ValueError("Invalid recorded repository revision")
    with tempfile.TemporaryDirectory(prefix="plancheck-replay-") as directory:
        payload = subprocess.check_output(["git", "archive", revision, "src"])
        with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
            for member in archive.getmembers():
                if (
                    member.name.startswith("/")
                    or ".." in Path(member.name).parts
                    or member.issym()
                    or member.islnk()
                ):
                    raise ValueError("Unsafe archive member")
            archive.extractall(directory)
        root = Path(directory) / "src" / "plancheck"
        hashes = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob("*.py"))
        }
        actual = hashlib.sha256(
            json.dumps(hashes, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        if actual != manifest["source_hash"]:
            raise ValueError(
                "Recorded source was dirty or differs from the archived revision; exact replay requires its saved source"
            )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(directory) / "src")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "plancheck.cli",
                "replay",
                "--run",
                str(args.run.resolve()),
                "--output",
                str(args.output.resolve()),
            ],
            env=environment,
            check=True,
        )


if __name__ == "__main__":
    main()
