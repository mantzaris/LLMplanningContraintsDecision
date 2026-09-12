"""Canonical serialization and immutable artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def json_response(raw: str) -> str:
    """Accept bare JSON or one complete Markdown JSON fence; never extract prose/code."""
    stripped = raw.strip()
    match = re.fullmatch(r"```(?:json)?\s*\n([\s\S]*?)\n```", stripped)
    return match.group(1).strip() if match else stripped


def immutable_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path.exists():
        if path.read_text() != encoded:
            raise ValueError(f"Refusing to overwrite immutable artifact: {path}")
        return
    with path.open("x") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
