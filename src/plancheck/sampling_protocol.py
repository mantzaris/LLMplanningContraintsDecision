"""Freeze Stage 3 from predeclared development size/timing rules, before fresh calls."""

from __future__ import annotations
import argparse
import math
import shutil
from pathlib import Path
from .budget import Journal
from .runner import source_hash, revision
from .sampling_run import protocol_prompts
from .util import read_json, immutable_json, digest, file_hash


def freeze(prepared: Path, development: Path, destination: Path, config_path: Path):
    events = Journal(development / "calls.jsonl").read()
    successes = [e["response"] for e in events if e["event"] == "generation_success"]
    starts = {e["key"]: e for e in events if e["event"] == "generation_start"}
    assert len(starts) <= 64
    responses = [e for e in events if e["event"] == "sampling_response"]
    sizes = {
        p: max((e["known_input_tokens"] for e in responses if e["purpose"] == p), default=0)
        for p in ("translation", "judgment")
    }
    if sizes["judgment"] == 0:
        sizes["judgment"] = read_json(development / "token-size-fallback.json")[
            "maximum_judgment_input_tokens"
        ]
    latencies = sorted(r["latency_seconds"] for r in successes)
    p95 = latencies[math.ceil(0.95 * len(latencies)) - 1]
    ledger = Journal(development.parent / "stage3-gpu-budget.jsonl").read()
    seconds = sum(e["elapsed_seconds"] for e in ledger if e["event"] == "session_end")
    requests = sum(e["event"] == "request_start" for e in ledger)
    forecasts = {str(n): n * 38 * p95 * 1.5 + 120 + n * 2 for n in (32, 24)}
    selected = next(
        (n for n in (32, 24) if forecasts[str(n)] <= 7080 - seconds and n * 38 <= 1500 - requests),
        None,
    )
    if selected is None:
        raise RuntimeError(
            "Even the predeclared 24-request pilot exceeds the remaining forecast budget"
        )
    cfg = read_json(Path("configs/sampling-development.json"))
    cfg.update(
        phase="fresh_exploratory",
        scenario_ids=[f"sampling-{i:02d}" for i in range(selected)],
        checkpoints=[2, 4, 8],
        generation_tokens=math.ceil(8 * (sizes["translation"] + 768) / 1000) * 1000,
        validation_tokens_per_prefix=math.ceil(2 * (sizes["judgment"] + 768) / 1000) * 1000,
        protocol_path=str(destination / "protocol.json"),
    )
    cfg["validation_tokens_total"] = cfg["validation_tokens_per_prefix"] * 3
    immutable_json(config_path, cfg)
    public = read_json(prepared / "public/scenarios.json")[:selected]
    for name, origin in {
        "references.json": "private/references.json",
        "annotation-review.csv": "private/annotation-review.csv",
        "automated-review.json": "private/review.json",
        "data-manifest.json": "manifest.json",
    }.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert target.read_bytes() == (prepared / origin).read_bytes()
        else:
            shutil.copyfile(prepared / origin, target)
    immutable_json(
        destination / "requests.json",
        [{k: v for k, v in s.items() if k != "stops"} for s in public],
    )
    immutable_json(destination / "prompts.json", protocol_prompts())
    immutable_json(
        destination / "protocol.json",
        {
            "version": "stage3-provisional-v1",
            "parent_revision": revision(),
            "source_hash_at_freeze": source_hash(),
            "config_hash": digest(cfg),
            "public_hash": digest(public),
            "prompt_hash": digest(protocol_prompts()),
            "reference_file_hash": file_hash(destination / "references.json"),
            "scenario_ids": cfg["scenario_ids"],
            "assigned_bases": selected,
            "replicates": 1,
            "development": {
                "run_manifest_hash": file_hash(development / "manifest.json"),
                "actual_calls": requests,
                "measured_gpu_seconds": seconds,
                "max_input_tokens": sizes,
                "p95_call_seconds": p95,
            },
            "forecast_seconds": forecasts,
            "scope_choice_before_fresh_outputs": selected,
            "metrics": ["bounded_reference_signature_coverage", "ordinary_final_plan_correctness"],
            "continuation": {
                "C_minus_each_baseline_coverage": 0.10,
                "C_minus_each_baseline_final_correctness": 0.05,
            },
            "selection": "balanced D, existing deterministic cost/tie rule, at most 2 judgments, no repairs",
            "generation": "A independent; B fixed perspectives; C same plus public behavior feedback; first 2 shared",
            "token_rule": "known input+output cap admission, actual I+O charge; failure reserves full; identical allocations",
            "validation_allocation": "equal nontransferable allocation per prefix; total is three allocations",
            "illustrations": "first C-only coverage gain, first C failure, first three-arm tie; fallback first ID",
            "inference_reference_access": False,
            "annotations": "provisional developer/automated; no independent human review",
            "stage_limits": {
                "actual_calls": 1500,
                "gpu_seconds": 7200,
                "measured_guard_seconds": 7080,
                "max_sessions": 4,
            },
        },
    )
    return cfg


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--prepared", type=Path, required=True)
    p.add_argument("--development", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("data/sampling"))
    p.add_argument("--config", type=Path, default=Path("configs/sampling.json"))
    a = p.parse_args()
    print(freeze(a.prepared, a.development, a.output, a.config))
