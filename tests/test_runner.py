import json
from pathlib import Path
import pytest
from plancheck.runner import run
from plancheck.util import immutable_json


def test_resume_does_not_load_gpu_or_read_references(scenario, pool, tmp_path, monkeypatch):
    public = tmp_path / "public"
    immutable_json(public / "scenarios.json", [scenario.model_dump(mode="json")])
    immutable_json(
        public / "pools" / f"{scenario.pool_hash}.json", [j.model_dump(mode="json") for j in pool]
    )
    config = json.loads(Path("configs/smoke.json").read_text())
    config.update(scenario_ids=[scenario.scenario_id], methods=["A"])
    saved = tmp_path / "saved"
    # The presence of a complete output is the resume unit. Never regenerate it.
    immutable_json(
        saved / "outputs" / f"{scenario.scenario_id}-A.json", {"retained": "completed output"}
    )
    import plancheck.runner as runner

    def forbidden(*args, **kwargs):
        raise AssertionError("GPU should not load on a completed resume")

    monkeypatch.setattr(runner, "TransformersGPU", forbidden)
    assert run(config, public, saved)["completed_outputs"] == 1
    before = (saved / "outputs" / f"{scenario.scenario_id}-A.json").read_bytes()
    assert run(config, public, saved)["completed_outputs"] == 1
    assert before == (saved / "outputs" / f"{scenario.scenario_id}-A.json").read_bytes()
    config["seed"] += 1
    with pytest.raises(ValueError, match="Resume manifest mismatch"):
        run(config, public, saved)


def test_held_out_refused_before_gpu(scenario, pool, tmp_path):
    from plancheck.util import immutable_json

    public = tmp_path / "public"
    held = scenario.model_copy(update={"split": "held_out"})
    immutable_json(public / "scenarios.json", [held.model_dump(mode="json")])
    immutable_json(
        public / "pools" / f"{held.pool_hash}.json", [j.model_dump(mode="json") for j in pool]
    )
    with pytest.raises(ValueError, match="held-out"):
        run({"scenario_ids": [held.scenario_id]}, public, tmp_path / "run")
