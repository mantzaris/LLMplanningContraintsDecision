"""Verify a local, read-only model cache against a pinned official manifest."""

from __future__ import annotations
import hashlib
from pathlib import Path
from .util import file_hash, read_json


def verify_model_cache(
    path: Path,
    identifier: str,
    revision: str,
    manifest_path: Path = Path("data/manifests/model.json"),
) -> dict:
    manifest = read_json(manifest_path)
    if manifest["model_id"] != identifier or manifest["revision"] != revision:
        raise ValueError("Model identifier/revision differs from official file manifest")
    verified = {}
    for record in manifest["files"]:
        name = record["rfilename"]
        if name == ".gitattributes":
            continue  # Repository packaging metadata is not used for inference.
        local = path / name
        if not local.is_file():
            raise ValueError(f"Model cache file missing: {name}")
        if record.get("lfs"):
            expected = record["lfs"]["sha256"]
            actual = file_hash(local)
        else:
            content = local.read_bytes()
            expected = record["blobId"]
            actual = hashlib.sha1(
                b"blob " + str(len(content)).encode() + b"\0" + content
            ).hexdigest()
        if actual != expected:
            raise ValueError(f"Model cache checksum mismatch: {name}")
        verified[name] = actual
    return {"model_id": identifier, "revision": revision, "verified_files": verified}
