#!/usr/bin/env python3
"""Checksum and package retained Stage 2 files locally; never claim remote replication.

The archive contains derived schedules and stays outside Git. Transfer to the established
remote storage is a separate authenticated operation, followed by checksum verification.
"""

from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import tarfile
from plancheck.util import digest, file_hash, immutable_json


def preserve(destination: Path) -> dict:
    roots = [Path("data/prepared/stage2")]
    roots.extend(
        sorted(
            p
            for p in Path("runs").iterdir()
            if p.is_dir()
            and p.name.startswith("stage2-")
            and not p.name.startswith("stage2-preservation")
        )
    )
    files = sorted({p for root in roots for p in root.rglob("*") if p.is_file()})
    files.extend([Path("runs/stage1-gpu-budget.jsonl"), Path("runs/stage2-gpu-budget.jsonl")])
    if any(p.is_symlink() for p in files):
        raise ValueError("Refusing to archive symlinked experimental files")
    entries = {str(p): {"sha256": file_hash(p), "bytes": p.stat().st_size} for p in files}
    source_manifest = {
        "format": 1,
        "files": entries,
        "total_files": len(entries),
        "total_bytes": sum(e["bytes"] for e in entries.values()),
        "excluded_large_objects": "raw GTFS ZIP, model caches and weights are retained separately, not copied into this archive",
    }
    immutable_json(destination / "source-manifest.json", source_manifest)
    archive = destination / "stage2-retained-artifacts.tar.gz"
    if not archive.exists():
        with tarfile.open(archive, mode="x:gz") as stream:
            for path in files:
                stream.add(path, arcname=str(path), recursive=False)
    # Read the actual archive bytes without extracting any paths or overwriting records.
    verified = {}
    with tarfile.open(archive, mode="r:gz") as stream:
        for member in stream:
            if not member.isfile() or member.name not in entries:
                raise ValueError("Unexpected archive member")
            payload = stream.extractfile(member)
            checksum = hashlib.sha256()
            size = 0
            for block in iter(lambda: payload.read(1024 * 1024), b""):
                checksum.update(block)
                size += len(block)
            verified[member.name] = {"sha256": checksum.hexdigest(), "bytes": size}
    if verified != entries:
        raise ValueError("Archive member checksums differ from original files")
    result = {
        "archive": str(archive),
        "archive_sha256": file_hash(archive),
        "archive_bytes": archive.stat().st_size,
        "source_manifest_sha256": digest(source_manifest),
        "verified_members": len(verified),
        "uncompressed_bytes": source_manifest["total_bytes"],
        "storage_status": "local archive verified; not independently or remotely replicated",
        "intended_remote_root": "/workspace/LLMplanningConstraintsStage2/preservation",
        "remote_replication_verified": False,
    }
    immutable_json(destination / "archive-verification.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.output.as_posix().startswith("runs/stage2-preservation"):
        raise ValueError("Use an ignored runs/stage2-preservation... directory")
    print(preserve(args.output))


if __name__ == "__main__":
    main()
