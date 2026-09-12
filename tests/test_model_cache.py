import hashlib
import pytest
from plancheck.model_cache import verify_model_cache
from plancheck.util import immutable_json


def test_model_cache_matches_identity_and_bytes(tmp_path):
    content = b"synthetic weights"
    (tmp_path / "weight").write_bytes(content)
    config = b"{}"
    (tmp_path / "config.json").write_bytes(config)
    manifest = tmp_path / "manifest.json"
    immutable_json(
        manifest,
        {
            "model_id": "fixture",
            "revision": "a" * 40,
            "files": [
                {"rfilename": "weight", "lfs": {"sha256": hashlib.sha256(content).hexdigest()}},
                {
                    "rfilename": "config.json",
                    "blobId": hashlib.sha1(b"blob 2\0" + config).hexdigest(),
                },
            ],
        },
    )
    assert len(verify_model_cache(tmp_path, "fixture", "a" * 40, manifest)["verified_files"]) == 2
    with pytest.raises(ValueError, match="identifier/revision"):
        verify_model_cache(tmp_path, "wrong", "a" * 40, manifest)
    (tmp_path / "weight").write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify_model_cache(tmp_path, "fixture", "a" * 40, manifest)
