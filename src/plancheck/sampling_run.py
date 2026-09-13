"""Stage 3 execution and exact saved-call replay using the existing model/solver tools."""

from __future__ import annotations
import argparse
from pathlib import Path
from .budget import BudgetExceeded, GPUBudget, Journal
from .model import ModelCalls, TransformersGPU, gpu_probe
from .model_cache import verify_model_cache
from .pilot import model_metadata
from .prompts import prompt_manifest
from .runner import load_public, revision, source_hash
from .semantic_sampling import (
    PERSPECTIVES,
    FEEDBACK_LIMIT,
    TokenCalls,
    sampling_prompt,
    parse_sample,
    prefix_bundle,
    validate_prefix,
)
from .util import digest, immutable_json, read_json, utc_now


def protocol_prompts():
    return {
        "base_and_judge": prompt_manifest(),
        "perspectives": PERSPECTIVES,
        "feedback_character_limit": FEEDBACK_LIMIT,
        "normalization": "source_only_existing_atom_value_v1",
    }


def run(config, public, directory, model_path=None, replay_from=None):
    scenarios, pools = load_public(public)
    by_id = {s.scenario_id: s for s in scenarios}
    selected = [by_id[sid] for sid in config["scenario_ids"]]
    assert config["checkpoints"] in ([2, 4], [2, 4, 8])
    assert (
        config["validation_tokens_total"]
        == len(config["checkpoints"]) * config["validation_tokens_per_prefix"]
    )
    assert all(s.split == "development" for s in selected)
    is_development = config["phase"] == "historical_development"
    if is_development:
        assert len(selected) <= 8 and set(config["scenario_ids"]).issubset(
            {f"pilot-{i:02d}" for i in range(48)}
        )
    else:
        frozen = read_json(Path(config["protocol_path"]))
        assert frozen["config_hash"] == digest(config)
        assert frozen["source_hash_at_freeze"] == source_hash()
        assert frozen["public_hash"] == digest([s.model_dump(mode="json") for s in selected])
    stable = {
        "config": config,
        "config_hash": digest(config),
        "source_hash": source_hash(),
        "prompt_hash": digest(protocol_prompts()),
        "model": model_metadata(config),
        "public_hash": digest([s.model_dump(mode="json") for s in selected]),
    }
    manifest_path = directory / "manifest.json"
    if manifest_path.exists():
        prior = read_json(manifest_path)
        assert all(prior[k] == v for k, v in stable.items()), "Resume mismatch"
    else:
        immutable_json(
            manifest_path,
            {
                **stable,
                "repository_revision": revision(),
                "created_at": utc_now(),
                "mode": "replay" if replay_from else config["phase"],
            },
        )
    if replay_from:
        prior = read_json(replay_from / "manifest.json")
        assert all(
            prior[k] == stable[k]
            for k in ("config_hash", "source_hash", "prompt_hash", "model", "public_hash")
        )
    immutable_json(
        directory / "public-scenarios.json", [s.model_dump(mode="json") for s in selected]
    )
    for s in selected:
        immutable_json(
            directory / "pools" / f"{s.pool_hash}.json",
            [j.model_dump(mode="json") for j in pools[s.pool_hash]],
        )
    journal = Journal(directory / "calls.jsonl")
    if replay_from and not journal.read():
        for event in Journal(replay_from / "calls.jsonl").read():
            if event["event"] in {
                "generation_start",
                "generation_success",
                "generation_error",
                "sampling_response",
            }:
                journal.append({**event, "copied_for_replay": True})
    budget = backend = None
    try:
        if not replay_from and not (directory / "completion.json").exists():
            assert model_path is not None
            immutable_json(
                directory / "model-file-verification.json",
                verify_model_cache(Path(model_path), config["model_id"], config["model_revision"]),
            )
            ledger = directory.parent / "stage3-gpu-budget.jsonl"
            starts = sum(e["event"] == "session_start" for e in Journal(ledger).read())
            if starts >= 4:
                raise BudgetExceeded("Four session uncertainty reserves exhausted")
            budget = GPUBudget(
                ledger, 1500, 7080, stage="stage3"
            )  # four possible 30s teardown margins
            backend = TransformersGPU(
                model_path, config["model_id"], config["model_revision"], budget
            )
            assert backend.metadata == stable["model"]
            immutable_json(
                directory / f"gpu-evidence-{budget.session}.json",
                {"before": backend.before, "loaded": backend.loaded},
            )
        calls = ModelCalls(journal, stable["model"], backend)
        token_calls = TokenCalls(
            calls, backend.count_prompt_tokens if backend else None, 64 if is_development else None
        )
        # Finish every sampling trajectory before any ordinary witness judgment.
        for scenario in selected:
            pool = pools[scenario.pool_hash]
            for arm in "ABC":
                samples, consumed, stopped = [], 0, None
                for index in range(max(config["checkpoints"])):
                    path = directory / "attempts" / scenario.scenario_id / arm / f"{index + 1}.json"
                    if path.exists():
                        sample = read_json(path)
                    else:
                        prompt = sampling_prompt(arm, index, scenario, pool, samples)
                        try:
                            call = token_calls.invoke(
                                prompt,
                                config["seed"] + index,
                                config["max_new_tokens"],
                                config["temperature"],
                                "translation",
                                f"{scenario.scenario_id}/{arm}/{index + 1}",
                                config["generation_tokens"] - consumed,
                            )
                        except BudgetExceeded as error:
                            if str(error) != "token_allowance_before_call":
                                raise
                            stopped = "generation_token_exhaustion"
                            break
                        sample = {
                            "index": index + 1,
                            "arm": arm,
                            "call": call,
                            "prompt_hash": digest(prompt),
                            **(
                                parse_sample(call["raw"], scenario, pool)
                                if not call["failed"]
                                else {
                                    "parse_status": "generation_failure",
                                    "formula": None,
                                    "signature": None,
                                    "clauses": [],
                                }
                            ),
                        }
                        immutable_json(path, sample)
                    samples.append(sample)
                    consumed += sample["call"]["charged_tokens"]
                immutable_json(
                    directory / "trajectories" / f"{scenario.scenario_id}-{arm}.json",
                    {
                        "scenario_id": scenario.scenario_id,
                        "arm": arm,
                        "samples": samples,
                        "generation_tokens": consumed,
                        "stop": stopped or "attempt_limit",
                    },
                )
            print(f"Sampled {scenario.scenario_id}", flush=True)
        immutable_json(
            directory / "generation-complete.json",
            {"scenario_ids": config["scenario_ids"], "arms": list("ABC")},
        )
        for scenario in selected:
            pool = pools[scenario.pool_hash]
            pair_path = directory / "pairs" / f"{scenario.scenario_id}.json"
            if pair_path.exists():
                continue
            results = {}
            for arm in "ABC":
                trajectory = read_json(
                    directory / "trajectories" / f"{scenario.scenario_id}-{arm}.json"
                )
                results[arm] = {}
                for count in config["checkpoints"]:
                    bundle_path = (
                        directory / "bundles" / scenario.scenario_id / f"{arm}-{count}.json"
                    )
                    if not bundle_path.exists():
                        bundle = (
                            read_json(
                                replay_from
                                / "bundles"
                                / scenario.scenario_id
                                / f"{arm}-{count}.json"
                            )
                            if replay_from
                            else prefix_bundle(
                                trajectory["samples"], count, pool, config["solver_timeout_ms"]
                            )
                        )
                        immutable_json(bundle_path, bundle)
                    bundle = read_json(bundle_path)
                    out = validate_prefix(
                        bundle,
                        scenario,
                        pool,
                        token_calls,
                        config,
                        f"{scenario.scenario_id}/{arm}/prefix-{count}",
                    )
                    out["generation_stop"] = trajectory["stop"]
                    out["checkpoint"] = count
                    results[arm][str(count)] = out
            immutable_json(pair_path, {"scenario_id": scenario.scenario_id, "outputs": results})
            print(f"Validated {scenario.scenario_id}", flush=True)
        immutable_json(
            directory / "completion.json", {"complete_bases": len(selected), "all_assigned": True}
        )
    except Exception as error:
        Journal(directory / "errors.jsonl").append(
            {"error_type": type(error).__name__, "error": str(error), "time": utc_now()}
        )
        raise
    finally:
        if backend is not None:
            backend.close()
            immutable_json(directory / f"gpu-after-{budget.session}.json", gpu_probe())
        elif budget is not None:
            budget.close()
    if replay_from:

        def stable_result(value):
            if isinstance(value, dict):
                return {
                    k: stable_result(v)
                    for k, v in value.items()
                    if k not in {"cached", "copied_for_replay"}
                }
            if isinstance(value, (list, tuple)):
                return [stable_result(v) for v in value]
            return value

        matches = {
            s.scenario_id: stable_result(read_json(directory / "pairs" / f"{s.scenario_id}.json"))
            == stable_result(read_json(replay_from / "pairs" / f"{s.scenario_id}.json"))
            for s in selected
        }
        immutable_json(directory / "replay-verification.json", matches)
        assert all(matches.values())
    return {"completed": len(selected)}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--public", type=Path, required=True)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--model-path")
    p.add_argument("--replay-from", type=Path)
    a = p.parse_args()
    print(run(read_json(a.config), a.public, a.run, a.model_path, a.replay_from))
