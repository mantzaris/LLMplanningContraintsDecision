"""Public-only paired pilot execution. Evaluation lives in pilot_analysis, separately."""

from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import math
import time
from .budget import GPUBudget, Journal, BudgetExceeded
from .methods import run_method
from .model import ModelCalls, TransformersGPU, gpu_probe
from .model_cache import verify_model_cache
from .prompts import prompt_manifest
from .runner import load_public, revision, source_hash
from .util import digest, immutable_json, read_json, utc_now


def method_config(config: dict, replicate: int) -> dict:
    return {
        **config,
        "seed": config["seed"] + replicate * 100000,
        "record_prefixes": True,
        "judgment_limit": 4,
        "repair_limit": 0,
        "method_call_limit": 8,
    }


def validation_prefix(output: dict, budget: int) -> dict:
    prefixes = output["validation_prefixes"]
    eligible = [int(n) for n in prefixes if int(n) <= budget]
    if not eligible:
        raise ValueError("Missing initial validation prefix")
    result = deepcopy(prefixes[str(max(eligible))])
    result["validation_budget"] = budget
    result["judgments_used"] = len(result["judgments"])
    return result


def forecast_scope(config: dict, latencies: list[float], remaining_seconds: float) -> dict:
    # Only timing of the diagnostic translation batch is inspected here, no labels/outcomes.
    ordered = sorted(latencies)
    p95 = ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)] if ordered else 3.2174
    seconds_per_call = max(p95, config["stage1_p95_seconds"]) * 1.5
    count, replicates = len(config["scenario_ids"]), config["replicates"]

    def upper(n, reps):
        return n * (12 * reps + reps + 3)  # shared 4 + D/E 4 each; B each; C replicate 0

    while count >= 6:
        total = upper(count, replicates)
        forecast = total * seconds_per_call + count * replicates * 2 + 120
        if forecast <= remaining_seconds and total <= config["gpu_request_limit"] - 64:
            return {
                "base_count": count,
                "replicates": replicates,
                "generation_upper_bound": total,
                "generation_p95_seconds": p95,
                "reserved_seconds_per_call": seconds_per_call,
                "forecast_seconds": forecast,
                "basis": "translation diagnostic timing only; no comparative outcomes",
            }
        if replicates > 1:
            replicates -= 1
        else:
            count -= 6
    raise BudgetExceeded("Even six paired base requests do not fit the conservative forecast")


def model_metadata(config):
    return {
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


def run_pilot(
    config: dict,
    public_dir: Path,
    run_dir: Path,
    *,
    model_path: str | None = None,
    replay_from: Path | None = None,
) -> dict:
    if config.get("judge_mode", "model") != "model":
        raise ValueError("Ordinary pilot permits model judgments only")
    if config["candidate_count"] != 4 or config.get("principal_repair_limit", 0) != 0:
        raise ValueError("Frozen pilot uses four candidates and elimination-only D/E")
    scenarios, pools = load_public(public_dir)
    by_id = {s.scenario_id: s for s in scenarios}
    selected = [by_id[key] for key in config["scenario_ids"]]
    if any(s.split != "development" for s in selected):
        raise ValueError("Pilot refuses validation and publication held-out requests")
    stable = {
        "config": config,
        "config_hash": digest(config),
        "source_hash": source_hash(),
        "prompt_hash": digest(prompt_manifest()),
        "model": model_metadata(config),
        "public_hash": digest([s.model_dump(mode="json") for s in selected]),
        "mode": "replay" if replay_from else "stage2_gpu_pilot",
    }
    if replay_from:
        previous = read_json(replay_from / "manifest.json")
        for key in ("config_hash", "public_hash", "prompt_hash", "source_hash", "model"):
            if previous[key] != stable[key]:
                raise ValueError(f"Replay mismatch: {key}; use the recorded source revision")
    manifest = run_dir / "manifest.json"
    if manifest.exists():
        previous = read_json(manifest)
        if any(previous[k] != v for k, v in stable.items()):
            raise ValueError("Resume manifest mismatch")
    else:
        immutable_json(
            manifest, {**stable, "repository_revision": revision(), "created_at": utc_now()}
        )
    immutable_json(run_dir / "public-scenarios.json", [s.model_dump(mode="json") for s in selected])
    for scenario in selected:
        immutable_json(
            run_dir / "pools" / f"{scenario.pool_hash}.json",
            [j.model_dump(mode="json") for j in pools[scenario.pool_hash]],
        )
    journal = Journal(run_dir / "calls.jsonl")
    if replay_from and not journal.read():
        for event in Journal(replay_from / "calls.jsonl").read():
            if event["event"] in {"generation_start", "generation_success", "generation_error"}:
                journal.append({**event, "copied_for_replay": True})
        immutable_json(run_dir / "scope.json", read_json(replay_from / "scope.json"))
    budget = backend = None
    try:
        if not replay_from and not (run_dir / "completion.json").exists():
            if model_path is None:
                raise ValueError("A verified local GPU model path is required")
            immutable_json(
                run_dir / "model-file-verification.json",
                verify_model_cache(Path(model_path), config["model_id"], config["model_revision"]),
            )
            budget = GPUBudget(
                run_dir.parent / "stage2-gpu-budget.jsonl",
                config["gpu_request_limit"],
                config["gpu_seconds_limit"],
                stage="stage2",
            )
            backend = TransformersGPU(
                model_path, config["model_id"], config["model_revision"], budget
            )
            if backend.metadata != stable["model"]:
                raise ValueError("GPU backend differs from frozen metadata")
            immutable_json(
                run_dir / f"gpu-evidence-{budget.session}.json",
                {"before": backend.before, "loaded": backend.loaded},
            )
        calls = ModelCalls(journal, stable["model"], backend)
        # Candidate-only diagnostic is part of the final sample and cached for both policies.
        if not (run_dir / "scope.json").exists():
            for scenario in selected[:4]:
                path = run_dir / "bundles" / f"{scenario.scenario_id}-r0.json"
                if not path.exists():
                    bundle = run_method(
                        "D",
                        scenario,
                        pools[scenario.pool_hash],
                        calls,
                        {**method_config(config, 0), "judgment_limit": 0},
                    )
                    immutable_json(path, bundle)
            latencies = [
                e["response"]["latency_seconds"]
                for e in journal.read()
                if e["event"] == "generation_success"
            ]
            scope = forecast_scope(config, latencies, budget.remaining())
            immutable_json(run_dir / "scope.json", scope)
        scope = read_json(run_dir / "scope.json")
        for replicate in range(scope["replicates"]):
            for scenario in selected[: scope["base_count"]]:
                identity = f"{scenario.scenario_id}-r{replicate}"
                path = run_dir / "pairs" / f"{identity}.json"
                if path.exists():
                    continue
                if budget:
                    reserve = 16 if replicate == 0 else 13
                    if (
                        budget.requests + reserve > budget.request_limit
                        or budget.remaining() < reserve * scope["reserved_seconds_per_call"] + 30
                    ):
                        journal.append(
                            {
                                "event": "stopped_before_pair",
                                "identity": identity,
                                "reason": "remaining conservative compute reservation",
                            }
                        )
                        return {
                            "status": "incomplete_budget",
                            "complete_pairs": len(list((run_dir / "pairs").glob("*.json"))),
                        }
                start = time.perf_counter()
                cfg = method_config(config, replicate)
                pool = pools[scenario.pool_hash]
                bundle_path = run_dir / "bundles" / f"{identity}.json"
                if not bundle_path.exists():
                    immutable_json(
                        bundle_path,
                        run_method("D", scenario, pool, calls, {**cfg, "judgment_limit": 0}),
                    )
                bundle = read_json(bundle_path)
                trajectories = {
                    method: run_method(method, scenario, pool, calls, cfg, bundle=bundle)
                    for method in ("D", "E")
                }
                outputs = {
                    method: {
                        str(b): validation_prefix(trajectories[method], b)
                        for b in config["validation_budgets"]
                    }
                    for method in ("D", "E")
                }
                secondary = {
                    method: run_method(
                        method,
                        scenario,
                        pool,
                        calls,
                        {**cfg, "record_prefixes": False, "repair_limit": 1, "judgment_limit": 2},
                    )
                    for method in ("ABC" if replicate == 0 else "AB")
                }
                immutable_json(
                    path,
                    {
                        "scenario_id": scenario.scenario_id,
                        "base_id": scenario.base_id,
                        "replicate": replicate,
                        "bundle_hash": digest(bundle),
                        "outputs": outputs,
                        "trajectories": trajectories,
                        "secondary": secondary,
                        "actual_pair_wall_seconds": time.perf_counter() - start,
                    },
                )
                print(f"checkpoint {identity}", flush=True)
        completed = len(list((run_dir / "pairs").glob("*.json")))
        result = {"status": "complete", "complete_pairs": completed, "scope": scope}
        immutable_json(run_dir / "completion.json", result)
        return result
    finally:
        if backend:
            session = budget.session
            backend.close()
            immutable_json(run_dir / f"gpu-after-{session}.json", gpu_probe())
        elif budget:
            budget.close()


def replay_pilot(run: Path, destination: Path) -> dict:
    manifest = read_json(run / "manifest.json")
    public = destination / "inputs"
    immutable_json(public / "scenarios.json", read_json(run / "public-scenarios.json"))
    for path in (run / "pools").glob("*.json"):
        immutable_json(public / "pools" / path.name, read_json(path))
    run_pilot(manifest["config"], public, destination, replay_from=run)

    def decision(value):
        if isinstance(value, dict):
            return {
                k: decision(v)
                for k, v in value.items()
                if k
                not in {
                    "logical_calls",
                    "solver_seconds",
                    "actual_pair_wall_seconds",
                    "bundle_hash",
                }
            }
        if isinstance(value, list):
            return [decision(v) for v in value]
        return value

    comparisons = {
        p.name: decision(read_json(p)) == decision(read_json(destination / "pairs" / p.name))
        for p in (run / "pairs").glob("*.json")
    }
    immutable_json(destination / "replay-verification.json", comparisons)
    if not all(comparisons.values()):
        raise ValueError("Saved pilot decisions did not replay exactly")
    return {"matching_pairs": len(comparisons)}
