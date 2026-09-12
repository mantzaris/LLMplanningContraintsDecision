"""Immutable, resumable inference artifacts and offline replay."""

from __future__ import annotations
import json
import subprocess
import time
from pathlib import Path
from .budget import GPUBudget, Journal
from .domain import Journey, PublicScenario
from .methods import run_method
from .model import ModelCalls, TransformersGPU, gpu_probe
from .model_cache import verify_model_cache
from .prompts import prompt_manifest
from .util import digest, file_hash, immutable_json, read_json, utc_now


def source_hash() -> str:
    root = Path(__file__).parent
    return digest({p.name: file_hash(p) for p in sorted(root.glob("*.py"))})


def revision() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def load_public(directory: Path) -> tuple[list[PublicScenario], dict[str, list[Journey]]]:
    scenarios = [
        PublicScenario.model_validate_json(json.dumps(row))
        for row in read_json(directory / "scenarios.json")
    ]
    pools = {}
    for scenario in scenarios:
        if scenario.pool_hash not in pools:
            rows = read_json(directory / "pools" / f"{scenario.pool_hash}.json")
            if digest(rows) != scenario.pool_hash:
                raise ValueError("Public pool checksum mismatch")
            pools[scenario.pool_hash] = [Journey.model_validate_json(json.dumps(j)) for j in rows]
    return scenarios, pools


def run(
    config: dict,
    public_dir: Path,
    run_dir: Path,
    model_path: str | None = None,
    replay_from: Path | None = None,
    cache_from: Path | None = None,
) -> dict:
    if config.get("judge_mode", "model") != "model":
        raise ValueError(
            "Ordinary inference supports model judgments only; use separate diagnostic module for gold"
        )
    scenarios, pools = load_public(public_dir)
    selected = [s for s in scenarios if s.scenario_id in config["scenario_ids"]]
    if len(selected) != len(set(config["scenario_ids"])):
        raise ValueError("Unknown predeclared scenario IDs")
    if any(s.split == "held_out" for s in selected):
        raise ValueError("Stage 1 runner refuses held-out experiments")
    model_metadata = {
        "identifier": config["model_id"],
        "revision": config["model_revision"],
        "tokenizer": config["model_id"],
        "tokenizer_revision": config["model_revision"],
        "backend": "transformers",
        "precision": "bfloat16",
        "quantization": None,
        "transformers": "4.51.3",
        "torch": "2.8.0+cu128",
        "same_translation_judgment_model": True,
    }
    if replay_from:
        prior = read_json(replay_from / "manifest.json")
        model_metadata = prior["model"]
        if prior["config_hash"] != digest(config) or prior["public_hash"] != digest(
            [s.model_dump(mode="json") for s in selected]
        ):
            raise ValueError("Replay configuration or public data mismatch")
    manifest_path = run_dir / "manifest.json"
    stable = {
        "config": config,
        "config_hash": digest(config),
        "public_hash": digest([s.model_dump(mode="json") for s in selected]),
        "prompt_hash": digest(prompt_manifest()),
        "source_hash": source_hash(),
        "model": model_metadata,
        "mode": "replay" if replay_from else "gpu_smoke",
    }
    if manifest_path.exists():
        prior = read_json(manifest_path)
        for key in stable:
            if prior[key] != stable[key]:
                raise ValueError(f"Resume manifest mismatch: {key}")
    else:
        immutable_json(
            manifest_path,
            {
                **stable,
                "repository_revision": revision(),
                "created_at": utc_now(),
                "working_tree_dirty": bool(
                    subprocess.check_output(["git", "status", "--porcelain"], text=True)
                ),
                "replay_source": str(replay_from) if replay_from else None,
            },
        )
    # Snapshot only inference inputs. No reference directory is opened here.
    immutable_json(run_dir / "public-scenarios.json", [s.model_dump(mode="json") for s in selected])
    for scenario in selected:
        immutable_json(
            run_dir / "pools" / f"{scenario.pool_hash}.json",
            [j.model_dump(mode="json") for j in pools[scenario.pool_hash]],
        )
    journal = Journal(run_dir / "calls.jsonl")
    cache_source = replay_from or cache_from
    if cache_source and not journal.path.exists():
        cache_manifest = read_json(cache_source / "manifest.json")
        if cache_manifest["model"] != model_metadata or cache_manifest["config_hash"] != digest(
            config
        ):
            raise ValueError("Cache source model/config mismatch")
        for event in Journal(cache_source / "calls.jsonl").read():
            if event["event"] in {"generation_start", "generation_success", "generation_error"}:
                journal.append(
                    {**event, "copied_for_replay": True, "cache_source_run": cache_source.name}
                )
    backend = None
    budget = None
    pending = [
        (s, method)
        for s in selected
        for method in config["methods"]
        if not (run_dir / "outputs" / f"{s.scenario_id}-{method}.json").exists()
    ]
    try:
        if pending and not replay_from:
            if model_path is None:
                raise ValueError("GPU smoke needs a local verified model path")
            immutable_json(
                run_dir / "model-file-verification.json",
                verify_model_cache(Path(model_path), config["model_id"], config["model_revision"]),
            )
            budget = GPUBudget(
                run_dir.parent / "stage1-gpu-budget.jsonl",
                config["gpu_request_limit"],
                config["gpu_seconds_limit"],
            )
            backend = TransformersGPU(
                model_path, config["model_id"], config["model_revision"], budget
            )
            if backend.metadata != model_metadata:
                raise ValueError("Installed GPU backend does not match frozen model metadata")
            immutable_json(
                run_dir / f"gpu-evidence-{budget.session}.json",
                {"before": backend.before, "loaded": backend.loaded},
            )
        calls = ModelCalls(journal, model_metadata, backend)
        for scenario, method in pending:
            start = time.perf_counter()
            result = run_method(method, scenario, pools[scenario.pool_hash], calls, config)
            result["method_wall_seconds"] = time.perf_counter() - start
            result["mode"] = stable["mode"]
            immutable_json(run_dir / "outputs" / f"{scenario.scenario_id}-{method}.json", result)
            print(
                f"{scenario.scenario_id} {method}: {result['status']} / {result['semantic_status']}",
                flush=True,
            )
    finally:
        if backend:
            session = budget.session
            backend.close()
            immutable_json(run_dir / f"gpu-after-{session}.json", gpu_probe())
        elif budget:
            budget.close()
    return {
        "run_dir": str(run_dir),
        "completed_outputs": len(list((run_dir / "outputs").glob("*.json"))),
    }


def replay(run_dir: Path, destination: Path) -> dict:
    # Materialize public-only layout from saved outputs; no feed or GPU required.
    manifest = read_json(run_dir / "manifest.json")
    public = destination / "replay-inputs"
    immutable_json(public / "scenarios.json", read_json(run_dir / "public-scenarios.json"))
    for path in (run_dir / "pools").glob("*.json"):
        immutable_json(public / "pools" / path.name, read_json(path))
    result = run(manifest["config"], public, destination, replay_from=run_dir)

    # Compare decisions, errors, scores and judgments, excluding hardware-dependent timings/cost cache flags.
    def decisions(value):
        if isinstance(value, dict):
            return {
                k: decisions(v)
                for k, v in value.items()
                if k not in {"method_wall_seconds", "solver_seconds", "mode", "logical_calls"}
            }
        if isinstance(value, list):
            return [decisions(v) for v in value]
        return value

    comparisons = {
        p.name: decisions(read_json(p)) == decisions(read_json(destination / "outputs" / p.name))
        for p in (run_dir / "outputs").glob("*.json")
    }
    immutable_json(destination / "replay-verification.json", comparisons)
    if not all(comparisons.values()):
        raise ValueError("Replay decision mismatch; inspect saved verification")
    return result
