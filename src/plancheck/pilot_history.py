"""New CPU analysis identity for prior saved model calls; no GPU backend available."""

from pathlib import Path
from .budget import Journal
from .methods import run_method
from .model import ModelCalls
from .pilot import validation_prefix
from .runner import load_public, revision, source_hash
from .prompts import prompt_manifest
from .util import digest, immutable_json, read_json


def reanalyze_history(prior: Path, destination: Path) -> dict:
    previous = read_json(prior / "manifest.json")
    config = {
        **previous["config"],
        "judgment_limit": 4,
        "repair_limit": 0,
        "principal_repair_limit": 0,
        "record_prefixes": True,
        "replicates": 1,
        "validation_budgets": [0, 1, 2, 4],
        "method_call_limit": 8,
    }
    public = destination / "inputs"
    immutable_json(public / "scenarios.json", read_json(prior / "public-scenarios.json"))
    for path in (prior / "pools").glob("*.json"):
        immutable_json(public / "pools" / path.name, read_json(path))
    scenarios, pools = load_public(public)
    by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    # Stage 1 public storage order differed from the declared execution order.
    # Hash and snapshot the pilot's declared order, as run_pilot does on replay.
    scenarios = [by_id[identifier] for identifier in config["scenario_ids"]]
    journal = Journal(destination / "calls.jsonl")
    if not journal.read():
        for event in Journal(prior / "calls.jsonl").read():
            if event["event"] in {"generation_start", "generation_success", "generation_error"}:
                journal.append({**event, "copied_for_replay": True})
    manifest = {
        "config": config,
        "config_hash": digest(config),
        "model": previous["model"],
        "mode": "stage1_saved_output_reanalysis_not_fresh_pilot",
        "repository_revision": revision(),
        "source_hash": source_hash(),
        "prompt_hash": digest(prompt_manifest()),
        "public_hash": digest([s.model_dump(mode="json") for s in scenarios]),
        "source_run_manifest_hash": digest(previous),
        "actual_new_generations": 0,
    }
    immutable_json(destination / "manifest.json", manifest)
    immutable_json(
        destination / "scope.json",
        {
            "base_count": len(scenarios),
            "replicates": 1,
            "basis": "all four prior Stage 1 sampled requests; no new sampling",
        },
    )
    immutable_json(
        destination / "public-scenarios.json", [s.model_dump(mode="json") for s in scenarios]
    )
    for path in (public / "pools").glob("*.json"):
        immutable_json(destination / "pools" / path.name, read_json(path))
    calls = ModelCalls(journal, previous["model"])
    for scenario in scenarios:
        identity = f"{scenario.scenario_id}-r0.json"
        if (destination / "pairs" / identity).exists():
            continue
        pool = pools[scenario.pool_hash]
        bundle = run_method("D", scenario, pool, calls, {**config, "judgment_limit": 0})
        immutable_json(destination / "bundles" / identity, bundle)
        trajectories = {
            m: run_method(m, scenario, pool, calls, config, bundle=bundle) for m in "DE"
        }
        outputs = {
            m: {str(b): validation_prefix(trajectories[m], b) for b in (0, 1, 2, 4)} for m in "DE"
        }
        # Missing cache is an error, never silently counted as new model evidence.
        if any(e.get("status") == "KeyError" for t in trajectories.values() for e in t["errors"]):
            raise ValueError("Historical reanalysis requires an uncached model call")
        secondary = {
            m: run_method(
                m,
                scenario,
                pool,
                calls,
                {**config, "record_prefixes": False, "repair_limit": 1, "judgment_limit": 2},
            )
            for m in "ABC"
        }
        immutable_json(
            destination / "pairs" / identity,
            {
                "scenario_id": scenario.scenario_id,
                "base_id": scenario.base_id,
                "replicate": 0,
                "bundle_hash": digest(bundle),
                "outputs": outputs,
                "trajectories": trajectories,
                "secondary": secondary,
                "actual_pair_wall_seconds": None,
            },
        )
    result = {
        "pairs": len(scenarios),
        "actual_new_generations": 0,
        "mode": "historical CPU reanalysis; not the 48-request pilot",
    }
    immutable_json(destination / "completion.json", result)
    return result
