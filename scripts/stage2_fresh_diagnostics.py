#!/usr/bin/env python3
"""Offline candidate/judge diagnostics for the unchanged frozen pilot.

No annotations or diagnostic values enter ordinary inference. Selection and oracle
execution are provided by the existing package; this script audits saved artifacts.
"""

from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from pathlib import Path
from plancheck.budget import Journal
from plancheck.compiler import predicate
from plancheck.constraints import InterpretationError, parse_interpretation, syntax_key
from plancheck.judgment import labels_from_judgments
from plancheck.pilot_analysis import classify, is_correct
from plancheck.prompts import judgment_prompt
from plancheck.reference import check_reference
from plancheck.runner import load_public
from plancheck.selection import restore_candidates, select_witness
from plancheck.selector_audit import profile_bundle
from plancheck.util import canonical, digest, immutable_json, read_json


def audit_trajectory(output: dict, bundle: dict, scenario, pool: list, reference: dict) -> dict:
    active = restore_candidates(bundle["candidates"])
    used = set()
    steps = []
    for number, (saved_witness, judgment) in enumerate(
        zip(output["witnesses"], output["judgments"])
    ):
        calculated = select_witness(
            active, pool, used, "balanced" if output["method"] == "D" else "consequence"
        )
        if canonical(calculated) != canonical(saved_witness):
            raise ValueError(
                f"Selection replay mismatch: {scenario.scenario_id}/{output['method']}/{number}"
            )
        journey = next(j for j in pool if j.journey_id == saved_witness["journey_id"])
        if judgment["journey_id"] != journey.journey_id:
            raise ValueError("Witness/judgment identity mismatch")
        label = check_reference(reference, journey)
        equivalent_before = [
            c.candidate_id
            for c in active
            if all(c.accepts(j.journey_id) == check_reference(reference, j) for j in pool)
        ]
        labels, contradictions = labels_from_judgments(output["judgments"][: number + 1])
        updated = (
            []
            if contradictions
            else [
                c for c in active if all(c.accepts(jid) == value for jid, value in labels.items())
            ]
        )
        removed = [c.candidate_id for c in active if c not in updated]
        chosen_before = active[0].plan.plan_id if active else None
        chosen_after = updated[0].plan.plan_id if updated else None
        verdict = judgment["judgment"]["verdict"]
        steps.append(
            {
                "query_index": number + 1,
                "journey_id": journey.journey_id,
                "selected_score": saved_witness["score"],
                "separated_pairs": saved_witness["separated_pairs"],
                "verdict": verdict,
                "reference_label": label,
                "judgment_correct": None
                if verdict == "uncertain"
                else (verdict == "satisfied") == label,
                "supporting_spans": judgment["judgment"].get("spans", []),
                "active_before": [c.candidate_id for c in active],
                "active_after": [c.candidate_id for c in updated],
                "removed_candidates": removed,
                "reference_equivalent_candidates_removed": sorted(
                    set(equivalent_before) & set(removed)
                ),
                "chosen_plan_before": chosen_before,
                "chosen_plan_after": chosen_after,
                "prompt_hash": digest(judgment_prompt(scenario, journey)),
            }
        )
        used.add(journey.journey_id)
        active = updated
    return {
        "steps": steps,
        "witnesses_recomputed_exactly": True,
        "final_remaining_ids": [c.candidate_id for c in active],
        "wrong_judgments": sum(s["judgment_correct"] is False for s in steps),
        "uncertain_judgments": sum(s["judgment_correct"] is None for s in steps),
        "equivalent_candidate_eliminations": sum(
            bool(s["reference_equivalent_candidates_removed"]) for s in steps
        ),
    }


def analyze(run: Path, analysis: Path, public: Path, references: Path, destination: Path) -> dict:
    scenarios, pools = load_public(public)
    by_id = {s.scenario_id: s for s in scenarios}
    refs = {r["scenario_id"]: r for r in read_json(references)}
    manifest = read_json(run / "manifest.json")
    events = Journal(run / "calls.jsonl").read()
    generation_starts = {e["key"]: e for e in events if e["event"] == "generation_start"}
    rows, trajectories, baseline_rows = [], [], []
    prompt_checks = 0
    for path in sorted((run / "pairs").glob("*.json")):
        pair = read_json(path)
        bundle = read_json(run / "bundles" / path.name)
        scenario = by_id[pair["scenario_id"]]
        pool = pools[scenario.pool_hash]
        reference = refs[scenario.scenario_id]["reference"]
        feasible = {j.journey_id for j in pool if check_reference(reference, j)}
        truth = tuple(j.journey_id in feasible for j in pool)
        active = restore_candidates(bundle["candidates"])
        profile = profile_bundle(bundle, scenario, pool)
        parsed = []
        for index, raw in enumerate(bundle["translations"]):
            try:
                expression = parse_interpretation(raw, scenario)
                signature = tuple(predicate(expression, j) for j in pool)
                parsed.append(
                    {
                        "raw_index": index,
                        "syntax_hash": digest(syntax_key(expression)),
                        "signature_hash": digest(signature),
                        "reference_equivalent": signature == truth,
                    }
                )
            except InterpretationError:
                pass
        by_signature = defaultdict(set)
        for item in parsed:
            by_signature[item["signature_hash"]].add(item["syntax_hash"])
        equivalents = [c.candidate_id for c in active if c.signature == truth]
        correct_plans = [c.candidate_id for c in active if c.plan.plan_id in feasible]
        initial = (
            bundle["candidates"][0]["plan"]
            if bundle["candidates"]
            else {"status": "unresolved", "plan_id": None}
        )
        initial_correct = is_correct(
            classify(
                {
                    "status": initial["status"],
                    "plan_id": initial["plan_id"],
                    "errors": bundle.get("errors", []),
                    "candidates": bundle["candidates"],
                },
                feasible,
            )
        )
        by_candidate = {c.candidate_id: c for c in active}
        pair_diagnostics = []
        for item in profile["pairs"]:
            left, right = by_candidate[item["left"]], by_candidate[item["right"]]
            pair_diagnostics.append(
                {
                    **item,
                    "left_plan_rejected_by_right": None
                    if left.plan.plan_id is None
                    else not right.accepts(left.plan.plan_id),
                    "right_plan_rejected_by_left": None
                    if right.plan.plan_id is None
                    else not left.accepts(right.plan.plan_id),
                }
            )
        row = {
            "scenario_id": scenario.scenario_id,
            "base_id": scenario.base_id,
            "replicate": pair["replicate"],
            "family": refs[scenario.scenario_id]["family"],
            "pool_size": len(pool),
            "pool_complete": scenario.pool_complete,
            "requested_interpretations": manifest["config"]["candidate_count"],
            "returned_interpretations": len(bundle["translations"]),
            "parsed_interpretations": len(parsed),
            "exact_text_duplicates": len(bundle["translations"]) - len(set(bundle["translations"])),
            "canonical_formula_duplicates": len(parsed) - len({x["syntax_hash"] for x in parsed}),
            "semantic_classes": len(active),
            "pool_equivalent_distinct_syntax_groups": sum(
                len(v) > 1 for v in by_signature.values()
            ),
            "syntactic_variants_lost_to_pool_equivalence": sum(
                len(v) - 1 for v in by_signature.values()
            ),
            "distinguishable_alternatives": len(active) > 1,
            "candidate_plan_statuses": dict(Counter(c.plan.status for c in active)),
            "candidate_plans": [
                {
                    "candidate_id": c.candidate_id,
                    "status": c.plan.status,
                    "plan_id": c.plan.plan_id,
                    "reference_correct_plan": c.plan.plan_id in feasible,
                    "acceptance_count": sum(c.signature),
                }
                for c in active
            ],
            "cross_interpretation_pairs": pair_diagnostics,
            "decision_relevant_alternatives": any(p["impact"] > 0 for p in profile["pairs"]),
            "available_witnesses": profile["witness_count"],
            "consequence_weight_variation": profile["variable_weights"],
            "reference_equivalent_ids": equivalents,
            "reference_equivalent_present": bool(equivalents),
            "reference_feasible_count": len(feasible),
            "correct_selected_candidate_ids": correct_plans,
            "correct_selected_plan_without_equivalent": bool(correct_plans) and not equivalents,
            "initial_correct": initial_correct,
            "correcting_selected_plan_available": bool(correct_plans) and not initial_correct,
            "shared_wrong_journey_labels": sum(
                all(c.signature[i] != truth[i] for c in active) for i in range(len(pool))
            )
            if active
            else None,
            "model_outputs": {},
            "oracle_outputs": {},
            "parsed_candidates": parsed,
            "first_witness_differs": profile["different_choice"],
            "witness_ranking_differs": profile["different_ranking"],
            "balanced_top_tie_count": profile["balanced"]["top_tie_count"],
            "consequence_top_tie_count": profile["consequence"]["top_tie_count"],
        }
        oracle = read_json(analysis / "oracle" / path.name)
        for method in ("D", "E"):
            trajectory = pair["outputs"][method]["4"]
            if canonical(trajectory["candidates"]) != canonical(bundle["candidates"]):
                raise ValueError("Paired candidate bundle mismatch")
            audited = audit_trajectory(trajectory, bundle, scenario, pool, reference)
            trajectories.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "replicate": pair["replicate"],
                    "method": method,
                    **audited,
                }
            )
            for mode, output_map in (
                ("model_outputs", pair["outputs"]),
                ("oracle_outputs", oracle),
            ):
                row[mode][method] = {
                    str(b): {
                        "category": classify(output_map[method][str(b)], feasible),
                        "correct": is_correct(classify(output_map[method][str(b)], feasible)),
                        "plan_id": output_map[method][str(b)].get("plan_id"),
                        "status": output_map[method][str(b)]["status"],
                        "witnesses": [
                            w["journey_id"] for w in output_map[method][str(b)]["witnesses"]
                        ],
                    }
                    for b in (0, 1, 2, 4)
                }
            # Every judgment call key must point to the public-only deterministic prompt.
            expected_prompts = {digest(judgment_prompt(scenario, j)) for j in pool}
            for call in trajectory["logical_calls"]:
                if call["purpose"] == "judgment":
                    saved = generation_starts[call["key"]]
                    if digest(saved["prompt"]) not in expected_prompts:
                        raise ValueError("Unexpected ordinary judge input")
                    prompt_checks += 1
        row["trajectory_differs"] = (
            row["model_outputs"]["D"]["4"]["witnesses"]
            != row["model_outputs"]["E"]["4"]["witnesses"]
        )
        row["final_output_differs"] = any(
            row["model_outputs"]["D"]["4"][key] != row["model_outputs"]["E"]["4"][key]
            for key in ("plan_id", "status")
        )
        row["final_correctness_differs"] = (
            row["model_outputs"]["D"]["4"]["correct"] != row["model_outputs"]["E"]["4"]["correct"]
        )
        row["alternatives_but_same_trajectory"] = (
            row["distinguishable_alternatives"] and not row["trajectory_differs"]
        )
        row["different_trajectory_same_correctness"] = (
            row["trajectory_differs"] and not row["final_correctness_differs"]
        )
        row["ordinary_correct_plan_without_equivalent"] = not equivalents and any(
            row["model_outputs"][m]["4"]["plan_id"] in feasible for m in ("D", "E")
        )
        rows.append(row)
        for method, output in pair.get("secondary", {}).items():
            baseline_rows.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "replicate": pair["replicate"],
                    "method": method,
                    "outcome": classify(output, feasible),
                    "reference_feasible": bool(feasible),
                    "logical_calls": len(output["logical_calls"]),
                    "input_tokens": sum(
                        c.get("input_tokens") or 0 for c in output["logical_calls"]
                    ),
                    "output_tokens": sum(
                        c.get("output_tokens") or 0 for c in output["logical_calls"]
                    ),
                    "latency_seconds": sum(
                        c.get("latency_seconds", 0) for c in output["logical_calls"]
                    ),
                }
            )
    summary = {
        "bundles": len(rows),
        "base_requests": len({r["base_id"] for r in rows}),
        "definitions": {
            "distinguishable_alternatives": "at least two acceptance vectors in the frozen pool",
            "decision_relevant_alternatives": "at least one pair with positive cross-plan rejection score",
            "correcting_selected_plan_available": "initial resolution incorrect, at least one candidate-selected plan satisfies reference",
            "pool_equivalence_limit": "Different syntax with equal vectors need not be inequivalent outside the pool; no external-domain completeness claim.",
        },
        "counts": {
            key: sum(bool(r[key]) for r in rows)
            for key in (
                "distinguishable_alternatives",
                "decision_relevant_alternatives",
                "consequence_weight_variation",
                "reference_equivalent_present",
                "correct_selected_plan_without_equivalent",
                "correcting_selected_plan_available",
                "first_witness_differs",
                "witness_ranking_differs",
                "trajectory_differs",
                "final_output_differs",
                "final_correctness_differs",
                "alternatives_but_same_trajectory",
                "different_trajectory_same_correctness",
                "ordinary_correct_plan_without_equivalent",
            )
        },
        "totals": {
            key: sum(r[key] for r in rows)
            for key in (
                "requested_interpretations",
                "returned_interpretations",
                "parsed_interpretations",
                "exact_text_duplicates",
                "canonical_formula_duplicates",
                "syntactic_variants_lost_to_pool_equivalence",
            )
        },
        "semantic_class_histogram": dict(Counter(str(r["semantic_classes"]) for r in rows)),
        "wrong_judgments_logical_DE": sum(t["wrong_judgments"] for t in trajectories),
        "uncertain_judgments_logical_DE": sum(t["uncertain_judgments"] for t in trajectories),
        "equivalent_candidate_eliminations_logical_DE": sum(
            t["equivalent_candidate_eliminations"] for t in trajectories
        ),
        "ordinary_judgment_prompt_checks": prompt_checks,
        "witness_and_bundle_integrity": "every saved D/E witness score and candidate bundle checked exactly",
        "baseline_summary": {
            m: {
                "outputs": len([r for r in baseline_rows if r["method"] == m]),
                "outcomes": dict(Counter(r["outcome"] for r in baseline_rows if r["method"] == m)),
                "costs": {
                    k: sum(r[k] for r in baseline_rows if r["method"] == m)
                    for k in ("logical_calls", "input_tokens", "output_tokens", "latency_seconds")
                },
            }
            for m in ("A", "B", "C")
        },
    }
    representatives = {}
    for row in rows:
        for category, test in (
            (
                "useful_validation",
                any(
                    not row["model_outputs"][m]["0"]["correct"]
                    and row["model_outputs"][m]["4"]["correct"]
                    for m in ("D", "E")
                ),
            ),
            (
                "harmful_validation",
                any(
                    row["model_outputs"][m]["0"]["correct"]
                    and not row["model_outputs"][m]["4"]["correct"]
                    for m in ("D", "E")
                ),
            ),
            ("divergent_selection", row["trajectory_differs"]),
            (
                "wrong_without_alternatives",
                not row["initial_correct"] and not row["distinguishable_alternatives"],
            ),
            ("correct_plan_without_equivalent", row["ordinary_correct_plan_without_equivalent"]),
        ):
            if test:
                representatives.setdefault(
                    category, {"scenario_id": row["scenario_id"], "replicate": row["replicate"]}
                )
    summary["additional_representatives"] = {
        "rule": "first lexicographic scenario/replicate satisfying each named diagnostic condition; no choice by effect magnitude",
        "cases": representatives,
    }
    immutable_json(destination / "diagnostic-summary.json", summary)
    immutable_json(destination / "bundle-diagnostics.json", rows)
    immutable_json(destination / "trajectory-audit.json", trajectories)
    immutable_json(destination / "baseline-metrics.json", baseline_rows)
    supplemental_audit(run, destination, by_id, rows, trajectories, summary, events)
    return summary


def supplemental_audit(run, destination, scenarios, rows, trajectories, summary, events):
    """Publish schedule-free trace pointers, unique-call checks and cost breakdowns."""
    starts = {e["key"]: e for e in events if e["event"] == "generation_start"}
    successes = {e["key"]: e["response"] for e in events if e["event"] == "generation_success"}
    unique_judgments, trace_calls = {}, {}
    errors, sources, semantic_statuses = Counter(), Counter(), Counter()
    repair_totals = {m: Counter() for m in "ABC"}
    for row in rows:
        sid, rep = row["scenario_id"], row["replicate"]
        name = f"{sid}-r{rep}.json"
        pair, bundle = read_json(run / "pairs" / name), read_json(run / "bundles" / name)
        errors.update(e["status"] for e in bundle["errors"])
        for method in "DE":
            output = pair["outputs"][method]["4"]
            semantic_statuses[output["semantic_status"]] += 1
            calls = [c for c in output["logical_calls"] if c["purpose"] == "judgment"]
            audit = next(
                a
                for a in trajectories
                if (a["scenario_id"], a["replicate"], a["method"]) == (sid, rep, method)
            )
            assert len(calls) == len(audit["steps"]) == len(output["judgments"])
            trace_calls[(sid, rep, method)] = []
            for call, step, judgment in zip(calls, audit["steps"], output["judgments"]):
                key = call["key"]
                checked = {
                    "scenario_id": sid,
                    "replicate": rep,
                    "journey_id": step["journey_id"],
                    "reference_label": step["reference_label"],
                    "verdict": step["verdict"],
                    "correct": step["judgment_correct"],
                    "reason": judgment["judgment"]["reason"],
                    "spans": judgment["judgment"]["spans"],
                    "cited_request_text": [
                        scenarios[sid].request[s["start"] : s["end"]]
                        for s in judgment["judgment"]["spans"]
                    ],
                }
                if key in unique_judgments:
                    assert unique_judgments[key] == checked
                unique_judgments[key] = checked
                trace_calls[(sid, rep, method)].append({"call_key": key, **step, **checked})
        for method, output in pair.get("secondary", {}).items():
            repair_totals[method]["repair_attempts"] += len(output["repairs"])
    for judgment in unique_judgments.values():
        sources.update(judgment["cited_request_text"])
    by_purpose = {}
    for key, event in starts.items():
        purpose = event["purpose"]
        bucket = by_purpose.setdefault(purpose, Counter())
        bucket["attempts"] += 1
        if key in successes:
            response = successes[key]
            bucket["successes"] += 1
            for field in ("input_tokens", "output_tokens", "latency_seconds"):
                bucket[field] += response[field]
            bucket["truncated"] += bool(response["truncated"])
    selected = set(
        (v["scenario_id"], v["replicate"])
        for v in summary["additional_representatives"]["cases"].values()
    )
    selected.update(
        (r["scenario_id"], r["replicate"])
        for r in rows
        if r["trajectory_differs"]
        or any(
            r["model_outputs"][m]["4"]["correct"] != r["oracle_outputs"][m]["4"]["correct"]
            for m in "DE"
        )
    )
    traces = []
    for sid, rep in sorted(selected):
        row = next(r for r in rows if (r["scenario_id"], r["replicate"]) == (sid, rep))
        bundle = read_json(run / "bundles" / f"{sid}-r{rep}.json")
        traces.append(
            {
                "scenario_id": sid,
                "replicate": rep,
                "request": scenarios[sid].request,
                "bundle_path": f"bundles/{sid}-r{rep}.json",
                "pool_hash": scenarios[sid].pool_hash,
                "candidates": [
                    {k: c[k] for k in ("candidate_id", "formula", "aliases", "plan")}
                    for c in bundle["candidates"]
                ],
                "model_outputs": row["model_outputs"],
                "oracle_outputs": row["oracle_outputs"],
                "steps": {m: trace_calls[(sid, rep, m)] for m in "DE"},
                "diagnostic_reference_equivalent_ids": row["reference_equivalent_ids"],
            }
        )
    immutable_json(
        destination / "call-audit.json",
        {
            "actual_generations_by_purpose": by_purpose,
            "unique_DE_judgment_calls": len(unique_judgments),
            "unique_DE_verdicts": dict(Counter(j["verdict"] for j in unique_judgments.values())),
            "unique_DE_wrong_judgments": sum(
                j["correct"] is False for j in unique_judgments.values()
            ),
            "cited_request_text_frequency_unique_calls": sources,
            "DE_semantic_statuses_logical": semantic_statuses,
            "translation_interpretation_errors": errors,
            "secondary_repair_attempts": repair_totals,
            "every_success_output_device_cuda": all(
                r["output_device"] == "cuda:0" for r in successes.values()
            ),
            "source_evidence_limit": "Offsets are valid syntactically; relevance is not established. Repeated On 20 cites copy the prompt's example offsets.",
        },
    )
    immutable_json(
        destination / "diagnostic-traces.json",
        {
            "selection_rule": "First lexicographic named condition from diagnostic-summary, plus every D/E-divergent bundle and every bundle whose model/oracle final correctness differs. Includes useful, harmful and unchanged outcomes.",
            "schedule_policy": "No journey timetables or full prompts; hashes and run-relative pointers support retrieval from authorized raw storage.",
            "traces": traces,
        },
    )


def main():
    parser = argparse.ArgumentParser()
    for name in ("run", "analysis", "public", "references", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(analyze(args.run, args.analysis, args.public, args.references, args.output))


if __name__ == "__main__":
    main()
