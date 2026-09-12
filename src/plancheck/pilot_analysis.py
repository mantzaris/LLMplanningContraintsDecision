"""Offline evaluation/oracle diagnostic. Never imported by the ordinary pilot runtime."""

from __future__ import annotations
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
import csv
import random
from .methods import finalize_output
from .budget import Journal
from .reference import check_reference
from .runner import load_public
from .selection import restore_candidates, select_witness
from .selector_audit import profile_bundle
from .util import digest, immutable_json, read_json

OUTCOMES = (
    "correct_feasible_plan",
    "incorrect_plan",
    "correct_infeasibility",
    "false_infeasibility",
    "unresolved",
    "invalid_model_output",
    "solver_timeout",
    "infrastructure_failure",
)


def classify(output: dict, feasible: set[str]) -> str:
    if output.get("plan_id") is not None:
        return "correct_feasible_plan" if output["plan_id"] in feasible else "incorrect_plan"
    if output.get("status") == "infeasible_in_pool":
        return "false_infeasibility" if feasible else "correct_infeasibility"
    statuses = {output.get("status")} | {e.get("status") for e in output.get("errors", [])}
    if statuses & {"timeout", "solver_timeout"}:
        return "solver_timeout"
    if statuses & {"BudgetExceeded", "TimeoutError", "RuntimeError", "KeyError"}:
        return "infrastructure_failure"
    if not output.get("candidates") and statuses & {
        "malformed",
        "unsupported",
        "entity_resolution_failure",
    }:
        return "invalid_model_output"
    return "unresolved"


def is_correct(category: str) -> bool:
    return category in {"correct_feasible_plan", "correct_infeasibility"}


def oracle_prefixes(
    bundle: dict, pool: list, reference: dict, method: str, budgets=(0, 1, 2, 4)
) -> dict:
    """Privileged labels, elimination only, zero generation/repair calls. Separate output tree."""
    active = restore_candidates(bundle["candidates"])
    initial = active[0] if active else None
    output = deepcopy(bundle)
    output.pop("validation_prefixes", None)
    output.update(
        method=method,
        judgments=[],
        witnesses=[],
        events=[],
        repairs=[],
        logical_calls=deepcopy(bundle.get("logical_calls", [])),
        mode="oracle_diagnostic_no_model_repairs",
    )
    used, snapshots = set(), {}

    def save():
        result = deepcopy(output)
        # Clear any former selected plan before finalization after candidate exhaustion.
        for key in ("final_formula", "final_solver", "remaining_candidates"):
            result.pop(key, None)
        result.update(status="unresolved", plan_id=None, semantic_status="unverified")
        finalize_output(result, active, initial)
        if result["semantic_status"] == "resolved_by_model":
            result["semantic_status"] = "resolved_by_privileged_reference_judgment"
        snapshots[len(output["judgments"])] = result

    save()
    for _ in range(max(budgets)):
        witness = select_witness(active, pool, used, "balanced" if method == "D" else "consequence")
        if witness is None:
            output["events"].append("no_distinguishing_witness_in_completed_pool")
            save()
            break
        journey = next(j for j in pool if j.journey_id == witness["journey_id"])
        label = check_reference(reference, journey)
        used.add(journey.journey_id)
        output["witnesses"].append(witness)
        output["judgments"].append(
            {
                "journey_id": journey.journey_id,
                "judgment": {
                    "verdict": "satisfied" if label else "violated",
                    "spans": [],
                    "reason": "privileged independent reference evaluator",
                },
            }
        )
        active = [c for c in active if c.accepts(journey.journey_id) == label]
        if not active:
            output["events"].append("all_candidates_eliminated")
        save()
        if not active:
            break
    return {
        str(b): {**deepcopy(snapshots[max(n for n in snapshots if n <= b)]), "validation_budget": b}
        for b in budgets
    }


def base_bootstrap(differences: dict[str, list[float]], seed=2201, draws=10000):
    """Resample whole base requests with their generation replicates kept together."""
    means = [sum(v) / len(v) for _, v in sorted(differences.items())]
    if len(means) < 2:
        return None  # One OD group is not a basis for a useful uncertainty estimate.
    rng = random.Random(seed)
    values = sorted(sum(rng.choice(means) for _ in means) / len(means) for _ in range(draws))
    return [values[int(0.025 * draws)], values[int(0.975 * draws)]]


def metric_row(scenario, replicate, method, budget, output, reference, pool, mode):
    feasible = {j.journey_id for j in pool if check_reference(reference, j)}
    category = classify(output, feasible)
    initial = {
        **output,
        "plan_id": output.get("initial_plan_id"),
        "status": output.get("candidates", [{}])[0].get("plan", {}).get("status", "unresolved")
        if output.get("candidates")
        else "unresolved",
    }
    initial_correct = is_correct(classify(initial, feasible))
    logical = output.get("logical_calls", [])
    judgments = []
    for item in output.get("judgments", []):
        label = check_reference(
            reference, next(j for j in pool if j.journey_id == item["journey_id"])
        )
        verdict = item["judgment"]["verdict"]
        judgments.append(
            {
                "journey_id": item["journey_id"],
                "verdict": verdict,
                "reference_label": label,
                "correct": None if verdict == "uncertain" else (verdict == "satisfied") == label,
            }
        )
    return {
        "scenario_id": scenario.scenario_id,
        "base_id": scenario.base_id,
        "replicate": replicate,
        "method": method,
        "budget": budget,
        "mode": mode,
        "reference_feasible": bool(feasible),
        "reference_feasible_count": len(feasible),
        "outcome": category,
        "correct": is_correct(category),
        "semantic_status": output.get("semantic_status"),
        "initial_correct": initial_correct,
        "validation_improved": not initial_correct and is_correct(category),
        "validation_damaged": initial_correct and not is_correct(category),
        "repair_improved": bool(output.get("repairs"))
        and not initial_correct
        and is_correct(category),
        "repair_damaged": bool(output.get("repairs"))
        and initial_correct
        and not is_correct(category),
        "judgments": len(judgments),
        "judgment_checks": judgments,
        "logical_calls": len(logical),
        "logical_input_tokens": sum(r.get("input_tokens") or 0 for r in logical),
        "logical_output_tokens": sum(r.get("output_tokens") or 0 for r in logical),
        "logical_latency_seconds": sum(r.get("latency_seconds", 0) for r in logical),
        "logical_solver_seconds": sum(
            c["plan"]["solver_seconds"] for c in output.get("candidates", [])
        ),
        "unknown_failed_token_counts": sum(r.get("failed", False) for r in logical),
    }


def summarize(rows: list[dict], expected_base_ids: list[str]) -> dict:
    summaries = []
    for mode in sorted({r["mode"] for r in rows}):
        for budget in sorted({r["budget"] for r in rows if r["method"] in "DE"}):
            selected = [
                r
                for r in rows
                if r["mode"] == mode and r["budget"] == budget and r["method"] in "DE"
            ]
            lookup = {(r["scenario_id"], r["replicate"], r["method"]): r for r in selected}
            differences, wins, ties, losses = defaultdict(list), 0, 0, 0
            for (sid, rep, method), d in lookup.items():
                if method != "D" or (sid, rep, "E") not in lookup:
                    continue
                e = lookup[(sid, rep, "E")]
                diff = int(e["correct"]) - int(d["correct"])
                differences[d["base_id"]].append(diff)
                wins += diff > 0
                ties += diff == 0
                losses += diff < 0
            summary = {
                "mode": mode,
                "budget": budget,
                "paired_E_wins": wins,
                "paired_ties": ties,
                "paired_E_losses": losses,
                "base_groups": len(differences),
                "paired_difference": sum(sum(v) / len(v) for v in differences.values())
                / len(differences)
                if differences
                else None,
                "paired_difference_95pct_base_bootstrap": base_bootstrap(differences),
                "methods": {},
            }
            for method in ("D", "E"):
                data = [r for r in selected if r["method"] == method]
                grouped = defaultdict(list)
                for row in data:
                    grouped[row["base_id"]].append(int(row["correct"]))
                method_summary = {
                    "outputs": len(data),
                    "outcomes": dict(Counter(r["outcome"] for r in data)),
                    "correct_rate": sum(sum(v) / len(v) for v in grouped.values()) / len(grouped)
                    if grouped
                    else None,
                    "correct_rate_95pct_base_bootstrap": base_bootstrap(grouped),
                    "totals": {
                        key: sum(r[key] for r in data)
                        for key in (
                            "judgments",
                            "logical_calls",
                            "logical_input_tokens",
                            "logical_output_tokens",
                            "logical_latency_seconds",
                            "logical_solver_seconds",
                            "validation_improved",
                            "validation_damaged",
                            "repair_improved",
                            "repair_damaged",
                        )
                    },
                }
                for feasible in (True, False):
                    subset = [r for r in data if r["reference_feasible"] == feasible]
                    method_summary["feasible" if feasible else "infeasible"] = {
                        "outputs": len(subset),
                        "correct": sum(r["correct"] for r in subset),
                        "outcomes": dict(Counter(r["outcome"] for r in subset)),
                    }
                summary["methods"][method] = method_summary
            summaries.append(summary)
    observed = sorted({r["scenario_id"] for r in rows})
    return {
        "summaries": summaries,
        "expected_base_ids": expected_base_ids,
        "observed_ids": observed,
        "missing_ids": sorted(set(expected_base_ids) - set(observed)),
        "uncertainty": "exploratory percentile bootstrap over base groups; null with <2 groups",
        "incomplete_sample": "Missing outputs are disclosed; never fabricate their outcomes.",
    }


def analyze_pairs(run: Path, public: Path, references: Path, destination: Path) -> dict:
    scenarios, pools = load_public(public)
    by_id = {s.scenario_id: s for s in scenarios}
    refs = {r["scenario_id"]: r["reference"] for r in read_json(references)}
    rows, diagnostics, traces = [], [], []
    for path in sorted((run / "pairs").glob("*.json")):
        pair = read_json(path)
        scenario = by_id[pair["scenario_id"]]
        pool, reference = pools[scenario.pool_hash], refs[scenario.scenario_id]
        bundle = read_json(run / "bundles" / path.name)
        truth = tuple(check_reference(reference, j) for j in pool)
        profile = profile_bundle(bundle, scenario, pool)
        profile.update(
            scenario_id=scenario.scenario_id,
            base_id=scenario.base_id,
            replicate=pair["replicate"],
            reference_equivalent_candidate=any(
                tuple(c["signature"]) == truth for c in bundle["candidates"]
            ),
        )
        diagnostics.append(profile)
        oracle = {m: oracle_prefixes(bundle, pool, reference, m) for m in "DE"}
        immutable_json(destination / "oracle" / path.name, oracle)
        for mode, outputs in (("model_judged", pair["outputs"]), ("oracle_diagnostic", oracle)):
            for method, prefixes in outputs.items():
                for budget, output in prefixes.items():
                    rows.append(
                        metric_row(
                            scenario,
                            pair["replicate"],
                            method,
                            int(budget),
                            output,
                            reference,
                            pool,
                            mode,
                        )
                    )
        for method, output in pair.get("secondary", {}).items():
            rows.append(
                metric_row(
                    scenario, pair["replicate"], method, 0, output, reference, pool, "model_judged"
                )
            )
        diverged = [w["journey_id"] for w in pair["outputs"]["D"]["4"]["witnesses"]] != [
            w["journey_id"] for w in pair["outputs"]["E"]["4"]["witnesses"]
        ]
        profile["trajectory_diverged"] = diverged
        traces.append(
            {
                "scenario_id": scenario.scenario_id,
                "replicate": pair["replicate"],
                "request": scenario.request,
                "bundle": bundle,
                "outputs": pair["outputs"],
            }
        )
    manifest = read_json(run / "manifest.json")
    summary = summarize(rows, manifest["config"]["scenario_ids"])
    scope = read_json(run / "scope.json")
    expected_ids = manifest["config"]["scenario_ids"][: scope["base_count"]]
    expected_pairs = {(sid, rep) for sid in expected_ids for rep in range(scope["replicates"])}
    observed_pairs = {(d["scenario_id"], d["replicate"]) for d in diagnostics}
    summary["frozen_scope"] = scope
    summary["missing_pairs"] = sorted(expected_pairs - observed_pairs)
    summary["primary_sample_complete"] = expected_pairs == observed_pairs
    summary["expected_pairs"] = len(expected_pairs)
    summary["observed_pairs"] = len(observed_pairs)
    # Incomplete samples do not silently acquire a complete-case primary estimate.
    summary["full_sample_correct_rate_bounds"] = []
    for item in summary["summaries"]:
        for method in "DE":
            relevant = [
                r
                for r in rows
                if r["mode"] == item["mode"]
                and r["budget"] == item["budget"]
                and r["method"] == method
            ]
            correct = sum(r["correct"] for r in relevant)
            denominator = len(expected_pairs)
            missing = denominator - len(relevant)
            summary["full_sample_correct_rate_bounds"].append(
                {
                    "mode": item["mode"],
                    "budget": item["budget"],
                    "method": method,
                    "lower": correct / denominator if denominator else None,
                    "upper": (correct + missing) / denominator if denominator else None,
                }
            )
    events = Journal(run / "calls.jsonl").read()
    actual = [e for e in events if not e.get("copied_for_replay")]
    successes = [e["response"] for e in actual if e["event"] == "generation_success"]
    summary["actual_new_compute"] = {
        "generation_attempts": sum(e["event"] == "generation_start" for e in actual),
        "generation_failures": sum(e["event"] == "generation_error" for e in actual),
        "input_tokens": sum(r["input_tokens"] for r in successes),
        "output_tokens": sum(r["output_tokens"] for r in successes),
        "generation_latency_seconds": sum(r["latency_seconds"] for r in successes),
        "gpu_accounting": "Use the separate stage allocation ledger for loading, idle and teardown time.",
        "failed_token_counts": "Unknown unless recorded; not assumed zero.",
    }
    divergence_ids = {
        (d["scenario_id"], d["replicate"]) for d in diagnostics if d["trajectory_diverged"]
    }
    summary["conditional_divergence_analysis"] = summarize(
        [r for r in rows if (r["scenario_id"], r["replicate"]) in divergence_ids],
        sorted({x[0] for x in divergence_ids}),
    )
    summary["diagnostic_counts"] = {
        "candidate_bundles": len(diagnostics),
        "reference_equivalent_bundles": sum(
            d["reference_equivalent_candidate"] for d in diagnostics
        ),
        "variable_weight_bundles": sum(d["variable_weights"] for d in diagnostics),
        "different_initial_choices": sum(d["different_choice"] for d in diagnostics),
        "diverged_trajectories": len(divergence_ids),
    }
    immutable_json(destination / "summary.json", summary)
    immutable_json(destination / "metrics.json", rows)
    immutable_json(destination / "selector-diagnostics.json", diagnostics)
    immutable_json(
        destination / "provenance.json",
        {
            "source_run_manifest_hash": digest(manifest),
            "reference_file_hash": digest(read_json(references)),
            "analysis": "offline; references inaccessible to inference",
        },
    )
    # Deterministic representatives: earliest tie/failure/divergence and earliest correct case.
    chosen = {}
    for trace in traces:
        sid, rep = trace["scenario_id"], trace["replicate"]
        final = [
            r
            for r in rows
            if r["scenario_id"] == sid
            and r["replicate"] == rep
            and r["budget"] == 4
            and r["mode"] == "model_judged"
            and r["method"] in "DE"
        ]
        categories = ["divergence" if (sid, rep) in divergence_ids else "tie"]
        if any(not r["correct"] for r in final):
            categories.append("failure")
        if any(r["correct"] for r in final):
            categories.append("correct")
        for category in categories:
            chosen.setdefault(category, trace)
    immutable_json(destination / "representative-traces.json", chosen)
    fields = [k for k in rows[0] if k != "judgment_checks"] if rows else []
    if rows and not (destination / "metrics.csv").exists():
        with (destination / "metrics.csv").open("x", newline="") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)
    return summary
