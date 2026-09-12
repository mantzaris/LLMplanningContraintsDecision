"""Pilot-specific risks: paired prefixes, degeneracy, accounting, label separation."""

import ast
import json
from pathlib import Path
import pytest
from plancheck.budget import GPUBudget, BudgetExceeded, Journal
from plancheck.constraints import ADAPTER, response_json
from plancheck.methods import run_method
from plancheck.model import ModelCalls
from plancheck.pilot import (
    validation_prefix,
    forecast_scope,
    run_pilot,
    replay_pilot,
    model_metadata,
)
from plancheck.pilot_analysis import oracle_prefixes, classify, base_bootstrap
from plancheck.pilot_review import review_wording
from plancheck.prompts import translation_prompt, judgment_prompt, prompt_manifest
from plancheck.runner import source_hash
from plancheck.selection import candidates, rank_witnesses
from plancheck.util import digest, immutable_json


def expression_for_mask(mask, pool):
    # A union of departure-time points expressed in the existing All/Not language.
    clauses = []
    for index, journey in enumerate(pool):
        if mask >> index & 1:
            bound = journey.rides[0].departure
            exact = {
                "kind": "all",
                "children": [
                    {"kind": "atom", "op": op, "scope": "outbound", "value": bound, "unit": "seconds"}
                    for op in ("depart_ge", "depart_le")
                ],
            }
            clauses.append({"kind": "not", "child": exact})
    return ADAPTER.validate_json(
        json.dumps({"kind": "not", "child": {"kind": "all", "children": clauses}})
    )


def test_supported_counterexample_and_constant_weight_degeneracy(pool):
    active = candidates([expression_for_mask(m, pool) for m in (1, 2, 5, 13)], pool)
    balanced = rank_witnesses(active, pool, set(), "balanced")
    consequence = rank_witnesses(active, pool, set(), "consequence")
    assert balanced[0]["journey_id"] == "c" and balanced[0]["score"] == 4
    assert consequence[0]["journey_id"] == "a" and consequence[0]["score"] == 9
    assert consequence[1]["journey_id"] == "b" and consequence[1]["score"] == 9
    # Exactly one interpretation pair => positive constant rescaling preserves ranking.
    for left in range(len(active)):
        for right in range(left + 1, len(active)):
            pair = [active[left], active[right]]
            assert [w["journey_id"] for w in rank_witnesses(pair, pool, set(), "balanced")] == [
                w["journey_id"] for w in rank_witnesses(pair, pool, set(), "consequence")
            ]


def injected_calls(scenario, pool, tmp_path):
    translations = [expression_for_mask(m, pool) for m in (1, 2, 5, 13)]

    class Injected:
        metadata = {"identifier": "injected logic test, not empirical model evidence"}

        def generate(self, prompt, seed, *args):
            if prompt == translation_prompt(scenario):
                raw = response_json(translations[seed - 104])
            elif prompt in {judgment_prompt(scenario, j) for j in pool}:
                journey = next(j for j in pool if judgment_prompt(scenario, j) == prompt)
                raw = json.dumps(
                    {
                        "verdict": "satisfied" if journey.journey_id == "b" else "violated",
                        "spans": [],
                        "reason": "injected",
                    }
                )
            else:
                raw = response_json(translations[0])
            return {"text": raw, "input_tokens": 12, "output_tokens": 8, "latency_seconds": 0.1}

    return ModelCalls(Journal(tmp_path / "calls.jsonl"), Injected.metadata, Injected())


CONFIG = {
    "candidate_count": 4,
    "method_call_limit": 8,
    "max_new_tokens": 768,
    "temperature": 0.7,
    "seed": 104,
    "solver_timeout_ms": 5000,
    "repair_limit": 0,
    "judgment_limit": 4,
    "record_prefixes": True,
}


def test_prefixes_match_fresh_limits_and_oracle_diagnostic(scenario, pool, tmp_path):
    calls = injected_calls(scenario, pool, tmp_path)
    bundle = run_method("D", scenario, pool, calls, {**CONFIG, "judgment_limit": 0})
    for method in "DE":
        trajectory = run_method(method, scenario, pool, calls, CONFIG, bundle=bundle)
        for budget in (0, 1, 2, 4):
            snapshot = validation_prefix(trajectory, budget)
            separate = run_method(
                method, scenario, pool, calls, {**CONFIG, "judgment_limit": budget}, bundle=bundle
            )
            for key in ("plan_id", "status", "judgments", "witnesses", "final_formula"):
                assert snapshot.get(key) == separate.get(key)
            assert len(snapshot["logical_calls"]) == 4 + len(snapshot["judgments"])
        # Reference singles out fixture b using its unique departure timestamp.
        reference = {
            "and": [
                {"requirement": "earliest_departure", "target": 120, "direction": "outbound"},
                {"requirement": "latest_departure", "target": 120, "direction": "outbound"},
            ]
        }
        oracle = oracle_prefixes(bundle, pool, reference, method)
        assert oracle["4"]["plan_id"] == "b"
        assert all(p["mode"] == "oracle_diagnostic_no_model_repairs" for p in oracle.values())
    assert calls.journal.read() and all(e.get("purpose") != "oracle" for e in calls.journal.read())


def test_stage_allocations_cannot_reset_history(tmp_path):
    old = tmp_path / "stage1.jsonl"
    first = GPUBudget(old)
    first.start()
    first.request()
    first.close()
    prior = old.read_bytes()
    with pytest.raises(ValueError, match="allocation"):
        GPUBudget(old, 1500, 7200, stage="stage2")
    assert old.read_bytes() == prior
    second = GPUBudget(tmp_path / "stage2.jsonl", 1500, 7200, stage="stage2")
    second.start()
    second.requests = 1500
    with pytest.raises(BudgetExceeded):
        second.request()
    second.close()
    with pytest.raises(ValueError):
        GPUBudget(tmp_path / "over", 1501, 7200, stage="stage2")
    cfg = {
        "scenario_ids": [str(n) for n in range(48)],
        "replicates": 2,
        "gpu_request_limit": 1500,
        "stage1_p95_seconds": 2.8164,
    }
    full = forecast_scope(cfg, [1.9, 2.1, 2.8], 7100)
    reduced = forecast_scope(cfg, [1.9, 2.1, 2.8], 4000)
    assert full["base_count"] == 48 and full["replicates"] == 2
    assert reduced["base_count"] == 48 and reduced["replicates"] == 1


def test_exclusive_categories_and_clustered_uncertainty():
    truth = {"a"}
    assert (
        classify({"plan_id": "a", "semantic_status": "unverified"}, truth)
        == "correct_feasible_plan"
    )
    assert classify({"status": "infeasible_in_pool"}, truth) == "false_infeasibility"
    assert classify({"status": "timeout"}, truth) == "solver_timeout"
    assert classify({"status": "malformed", "candidates": []}, truth) == "invalid_model_output"
    assert classify({"errors": [{"status": "RuntimeError"}]}, truth) == "infrastructure_failure"
    assert base_bootstrap({"one": [0, 1]}) is None
    assert base_bootstrap({"a": [1, -1], "b": [0, 0]}) == [0, 0]


def test_wording_reviewer_scope_and_midnight_units():
    request = "Endpoints]. On the return segment only, depart no earlier than 25:02:03."
    assert review_wording(request) == {
        "and": [{"requirement": "earliest_departure", "target": 90123, "direction": "return"}]
    }
    with pytest.raises(ValueError, match="Unreviewed wording"):
        review_wording("Endpoints]. Depart whenever convenient.")


def test_pilot_reference_import_boundary(tmp_path):
    package = Path(__file__).parents[1] / "src/plancheck"
    forbidden = {
        "reference",
        "evaluation",
        "diagnostic",
        "pilot_analysis",
        "pilot_review",
        "pilot_data",
        "pilot_protocol",
    }
    for name in ("pilot", "methods", "model", "selection", "prompts", "runner"):
        tree = ast.parse((package / f"{name}.py").read_text())
        assert not any(
            isinstance(n, ast.ImportFrom) and n.module in forbidden for n in ast.walk(tree)
        )
    with pytest.raises(ValueError, match="model judgments only"):
        run_pilot({"judge_mode": "gold"}, tmp_path, tmp_path / "run")


def test_checkpoint_and_full_saved_replay(scenario, pool, tmp_path):
    # Seed a saved-generation journal explicitly as a synthetic test. No fake GPU claim.
    from plancheck.pilot import method_config

    prior = tmp_path / "prior"
    cfg = {
        **CONFIG,
        "scenario_ids": [scenario.scenario_id],
        "replicates": 1,
        "validation_budgets": [0, 1, 2, 4],
        "model_id": "Qwen/Qwen2.5-7B-Instruct",
        "model_revision": "test-only",
        "judge_mode": "model",
    }
    # Use production cache-key metadata, but mark every generated response as an injected fixture.
    calls = injected_calls(scenario, pool, prior)
    calls.metadata = model_metadata(cfg)
    bundle = run_method("D", scenario, pool, calls, {**method_config(cfg, 0), "judgment_limit": 0})
    for method in "DE":
        run_method(method, scenario, pool, calls, method_config(cfg, 0), bundle=bundle)
    for method in "ABC":
        run_method(
            method, scenario, pool, calls, {**CONFIG, "repair_limit": 1, "judgment_limit": 2}
        )
    public = tmp_path / "public"
    immutable_json(public / "scenarios.json", [scenario.model_dump(mode="json")])
    immutable_json(
        public / "pools" / f"{scenario.pool_hash}.json", [j.model_dump(mode="json") for j in pool]
    )
    manifest = {
        "config": cfg,
        "config_hash": digest(cfg),
        "source_hash": source_hash(),
        "prompt_hash": digest(prompt_manifest()),
        "model": model_metadata(cfg),
        "public_hash": digest([scenario.model_dump(mode="json")]),
    }
    immutable_json(prior / "manifest.json", manifest)
    immutable_json(prior / "scope.json", {"base_count": 1, "replicates": 1})
    run = tmp_path / "replay"
    assert run_pilot(cfg, public, run, replay_from=prior)["complete_pairs"] == 1
    size = (run / "calls.jsonl").stat().st_size
    assert run_pilot(cfg, public, run, replay_from=prior)["complete_pairs"] == 1
    assert (run / "calls.jsonl").stat().st_size == size
    assert replay_pilot(run, tmp_path / "again")["matching_pairs"] == 1
