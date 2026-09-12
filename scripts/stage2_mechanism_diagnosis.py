#!/usr/bin/env python3
"""CPU-only audit of fixed Stage 2 outputs; never instantiates an inference backend.

Reference labels occur only in offline evaluation and explicitly privileged replay.
The time-value sensitivity function accepts text and an AST, never reference labels.
"""

from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
from itertools import combinations
from pathlib import Path
import re

from plancheck.compiler import PlanResult, predicate
from plancheck.constraints import ADAPTER, InterpretationError, parse_interpretation, syntax_key
from plancheck.domain import objective
from plancheck.gtfs import Feed, Network, seconds
from plancheck.pilot_analysis import classify, is_correct, oracle_prefixes
from plancheck.pilot_review import review_wording
from plancheck.reference import check_reference
from plancheck.runner import load_public
from plancheck.selection import Candidate, consequence, rank_witnesses, restore_candidates
from plancheck.util import canonical, digest, file_hash, immutable_json, read_json

BUDGETS = (0, 1, 2, 4)


def atoms(formula):
    if formula["kind"] == "atom":
        yield formula
    elif formula["kind"] == "all":
        for child in formula["children"]:
            yield from atoms(child)
    else:
        yield from atoms(formula["child"])


def time_mentions(request: str) -> list[dict]:
    """Narrow source-only literal binding. Public window text is deliberately excluded.

    No nearest-number heuristic, op correction, scope correction, addition or deletion.
    Repeated/ambiguous bindings are refused by normalize_time_values.
    """
    pattern = re.compile(
        r"(?P<phrase>depart no earlier than|do not depart before|depart no later than|arrive by) "
        r"(?P<clock>\d{2,3}:[0-5]\d:[0-5]\d)",
        re.I,
    )
    names = {
        "depart no earlier than": "depart_ge",
        "do not depart before": "depart_ge",
        "depart no later than": "depart_le",
        "arrive by": "arrive_by",
    }
    found = []
    for match in pattern.finditer(request):
        sentence = request[request.rfind(".", 0, match.start()) + 1 : match.start()]
        scopes = re.findall(r"On the (outbound|return) segment only,", sentence, re.I)
        found.append(
            {
                "op": names[match["phrase"].lower()],
                "scope": scopes[-1].lower() if scopes else "outbound",
                "literal": match["clock"],
                "seconds": seconds(match["clock"]),
                "source": {"start": match.start(), "end": match.end()},
                "text": match.group(),
            }
        )
    return found


def normalize_time_values(request: str, expression):
    bindings = defaultdict(list)
    for mention in time_mentions(request):
        bindings[(mention["op"], mention["scope"])].append(mention)
    formula = expression.model_dump(mode="json")
    changes = []
    for atom in atoms(formula):
        options = bindings[(atom["op"], atom["scope"])]
        if atom["unit"] == "seconds" and len(options) == 1:
            mention = options[0]
            if atom["value"] != mention["seconds"]:
                changes.append({"predicted_atom": deepcopy(atom), "request_binding": mention})
                atom["value"] = mention["seconds"]
    return ADAPTER.validate_json(canonical(formula)), changes


def exact_candidates(expressions, pool):
    """Offline exact evaluation, same finite objective; no large Z3 encodings needed."""
    active, seen_syntax, seen_vectors = [], {}, {}
    ordered_indices = sorted(range(len(pool)), key=lambda i: objective(pool[i]))
    for index, expr in enumerate(expressions):
        alias, syntax = f"c{index}", syntax_key(expr)
        if syntax in seen_syntax:
            seen_syntax[syntax].aliases.append(alias)
            continue
        vector = tuple(predicate(expr, j) for j in pool)
        if vector in seen_vectors:
            seen_vectors[vector].aliases.append(alias)
            seen_syntax[syntax] = seen_vectors[vector]
            continue
        best = next((pool[i].journey_id for i in ordered_indices if vector[i]), None)
        c = Candidate(
            alias,
            expr,
            vector,
            tuple(j.journey_id for j in pool),
            PlanResult("satisfiable" if best else "infeasible_in_pool", best, 0),
            [alias],
        )
        active.append(c)
        seen_syntax[syntax] = seen_vectors[vector] = c
    return active


def partition(vector):
    inverse = tuple(not v for v in vector)
    return min(tuple(vector), inverse)


def selection_state(active, pool, used=frozenset()):
    patterns, partitions = Counter(), Counter()
    for journey in pool:
        if journey.journey_id in used:
            continue
        vector = tuple(c.accepts(journey.journey_id) for c in active)
        patterns["".join(str(int(v)) for v in vector)] += 1
        if vector and any(vector) and not all(vector):
            partitions["".join(str(int(v)) for v in partition(vector))] += 1
    pairs = [
        {
            "ids": [a.candidate_id, b.candidate_id],
            "I": consequence(a, b, {}),
            "weight": 1 + consequence(a, b, {}),
        }
        for a, b in combinations(active, 2)
    ]
    ranks = {
        m: rank_witnesses(active, pool, set(used), p)
        for m, p in [("D", "balanced"), ("E", "consequence")]
    }
    ids = {m: [r["journey_id"] for r in rank] for m, rank in ranks.items()}
    tops = {
        m: [r["journey_id"] for r in rank if r["score_numerator"] == rank[0]["score_numerator"]]
        if rank
        else []
        for m, rank in ranks.items()
    }
    constant = bool(pairs) and len({p["weight"] for p in pairs}) == 1
    return {
        "active_ids": [c.candidate_id for c in active],
        "patterns": dict(patterns),
        "witness_partitions": dict(partitions),
        "weights": pairs,
        "witness_count": len(ids["D"]),
        "constant_weights": constant,
        "single_partition": len(partitions) == 1,
        "same_ranking": ids["D"] == ids["E"],
        "same_choice": ids["D"][:1] == ids["E"][:1],
        "shared_top_tiebreak": bool(tops["D"])
        and len(tops["D"]) > 1
        and len(tops["E"]) > 1
        and ids["D"][0] == ids["E"][0],
        "top_ids": tops,
        "ranks": {
            m: [{k: r[k] for k in ("journey_id", "score_numerator", "cost")} for r in rank]
            for m, rank in ranks.items()
        },
    }


def kept_after(active, judgments):
    return [
        c
        for c in active
        if all(
            item["judgment"]["verdict"] == "uncertain"
            or c.accepts(item["journey_id"]) == (item["judgment"]["verdict"] == "satisfied")
            for item in judgments
        )
    ]


def output_category(output, good):
    return classify(output, good)


def state_at_budget(bundle, output, pool, budget):
    active = kept_after(restore_candidates(bundle["candidates"]), output["judgments"])
    available = selection_state(active, pool, {w["journey_id"] for w in output["witnesses"]})
    if not bundle["candidates"]:
        stop = "no_parsed_candidate"
    elif not active:
        stop = "candidate_exhaustion"
    elif available["witness_count"] == 0:
        stop = "one_class_no_witness" if len(active) == 1 else "witnesses_exhausted"
    else:
        stop = "judgment_budget_limit" if len(output["judgments"]) >= budget else "other_stop"
    return {
        "budget": budget,
        "stop": stop,
        "judgments": len(output["judgments"]),
        "remaining_ids": [c.candidate_id for c in active],
        "remaining_witnesses": available["witness_count"],
        "recorded_events": output["events"],
        "plan_id": output["plan_id"],
        "status": output["status"],
    }


def clause_effects(reference, pool):
    leaves = reference["and"]
    rows = []
    for index, rule in enumerate(leaves):
        accepted = sum(check_reference(rule, j) for j in pool)
        marginal = sum(
            not check_reference(rule, j)
            and all(check_reference(other, j) for i, other in enumerate(leaves) if i != index)
            for j in pool
        )
        rows.append(
            {
                "rule": rule,
                "accepted": accepted,
                "pool_size": len(pool),
                "effect": "always_true"
                if accepted == len(pool)
                else "always_false"
                if accepted == 0
                else "varies",
                "marginal_exclusions": marginal,
            }
        )
    return rows


def aggregate_ranking(active, pool):
    """Exact initial scores by acceptance pattern, avoiding quadratic ID lookups."""
    weights = {
        (a, b): 1 + consequence(active[a], active[b], {})
        for a, b in combinations(range(len(active)), 2)
    }
    groups = {}
    for i, journey in enumerate(pool):
        vector = tuple(c.signature[i] for c in active)
        if not vector or not any(vector) or all(vector):
            continue
        cut = [p for p in weights if vector[p[0]] != vector[p[1]]]
        key = "".join(str(int(v)) for v in vector)
        group = groups.setdefault(
            key,
            {
                "count": 0,
                "first_id": journey.journey_id,
                "D": len(cut),
                "E": sum(weights[p] for p in cut),
            },
        )
        group["count"] += 1
        group["first_id"] = min(group["first_id"], journey.journey_id)
    tops = {}
    for method in "DE":
        best = max((g[method] for g in groups.values()), default=0)
        top = [g for g in groups.values() if g[method] == best]
        tops[method] = {
            "score": best,
            "tie_count": sum(g["count"] for g in top),
            "chosen_id": min((g["first_id"] for g in top), default=None),
        }
    return {
        "weight_histogram": dict(Counter(weights.values())),
        "pattern_scores": groups,
        "top": tops,
        "different_first_choice": tops["D"]["chosen_id"] != tops["E"]["chosen_id"],
    }


def analyze(run, public, references, output, feed, data_config):
    scenarios, pools = load_public(public)
    refs = {r["scenario_id"]: r for r in read_json(references)}
    manifest = read_json(run / "manifest.json")
    fixed = read_json(Path("artifacts/stage2/pilot-v1/full-artifact-manifest.json"))
    for name, record in fixed["files"].items():
        assert file_hash(run / name) == record["sha256"], name
    ledger = Path("runs/stage2-gpu-budget.jsonl")
    ledger_before = file_hash(ledger)
    rows, budget_rows, failures, judgments, normalization, universe = [], [], [], {}, [], []
    assert file_hash(feed) == data_config["feed_sha256"]
    # Caps picked from public enumeration counts before this diagnostic: max segment
    # enumeration 1047; largest segment-count product 65296. No method labels prune it.
    expanded_config = {**data_config, "segment_pool_limit": 2000, "joint_pool_limit": 100000}
    network = Network(Feed(feed), date.fromisoformat(data_config["service_date"]), expanded_config)
    for scenario in scenarios:
        sid = scenario.scenario_id
        bundle = read_json(run / "bundles" / f"{sid}-r0.json")
        pair = read_json(run / "pairs" / f"{sid}-r0.json")
        pool, reference = pools[scenario.pool_hash], refs[sid]["reference"]
        assert review_wording(scenario.request) == reference
        good = {j.journey_id for j in pool if check_reference(reference, j)}
        active = restore_candidates(bundle["candidates"])
        exprs, parsed, normalized_exprs = [], [], []
        for index, raw in enumerate(bundle["translations"]):
            try:
                expr = parse_interpretation(raw, scenario)
            except InterpretationError as error:
                parsed.append({"raw_index": index, "error": error.status, "detail": str(error)})
                continue
            exprs.append(expr)
            normalized, changes = normalize_time_values(scenario.request, expr)
            normalized_exprs.append(normalized)
            parsed.append(
                {
                    "raw_index": index,
                    "formula": expr.model_dump(mode="json"),
                    "normalized_formula": normalized.model_dump(mode="json"),
                    "value_changes": changes,
                }
            )
        recomputed = exact_candidates(exprs, pool)
        assert [(c.signature, c.plan.status, c.plan.plan_id) for c in active] == [
            (c.signature, c.plan.status, c.plan.plan_id) for c in recomputed
        ]
        state = selection_state(active, pool)
        n = len(active)
        cause = (
            "no_parsed_candidate"
            if not n
            else "one_class"
            if n == 1
            else "two_classes"
            if n == 2
            else "uniform_weights_3plus"
            if state["constant_weights"]
            else "variable_weights_same_first"
            if state["same_choice"]
            else "different_first"
        )
        row = {
            "scenario_id": sid,
            "family": refs[sid]["family"],
            "request": scenario.request,
            "requested": manifest["config"]["candidate_count"],
            "parsed": len(exprs),
            "exact_text_duplicates": len(bundle["translations"]) - len(set(bundle["translations"])),
            "canonical_duplicates": len(exprs) - len({syntax_key(e) for e in exprs}),
            "semantic_classes": n,
            "pool_size": len(pool),
            "exclusive_equivalence_cause": cause,
            "initial_state": state,
            "budgets": {},
            "sequences": {},
            "query_states": {},
            "candidate_plans": [
                {
                    "id": c.candidate_id,
                    "formula": c.expression.model_dump(mode="json"),
                    "aliases": c.aliases,
                    "plan_id": c.plan.plan_id,
                    "selected_plan_reference_valid": c.plan.plan_id in good
                    if c.plan.plan_id is not None
                    else None,
                    "status": c.plan.status,
                    "accepted": sum(c.signature),
                    "reference_equivalent": c.signature
                    == tuple(j.journey_id in good for j in pool),
                }
                for c in active
            ],
        }
        oracle = {m: oracle_prefixes(bundle, pool, reference, m) for m in "DE"}
        for method in "DE":
            trajectory = pair["outputs"][method]["4"]
            row["sequences"][method] = [w["journey_id"] for w in trajectory["witnesses"]]
            row["query_states"][method] = []
            prefix_active, used = active, set()
            calls = [c for c in trajectory["logical_calls"] if c["purpose"] == "judgment"]
            for index, (witness, judgment, call) in enumerate(
                zip(trajectory["witnesses"], trajectory["judgments"], calls)
            ):
                step = selection_state(prefix_active, pool, used)
                assert step["ranks"][method][0]["journey_id"] == witness["journey_id"]
                step["selected"] = witness
                step["judgment"] = judgment["judgment"]
                after = kept_after(prefix_active, [judgment])
                step["after_ids"] = [c.candidate_id for c in after]
                step["before_plan_id"] = prefix_active[0].plan.plan_id
                step["after_plan_id"] = after[0].plan.plan_id if after else None
                row["query_states"][method].append(step)
                key = call["key"]
                verdict = judgment["judgment"]["verdict"]
                correct = (
                    None
                    if verdict == "uncertain"
                    else (verdict == "satisfied") == (witness["journey_id"] in good)
                )
                item = judgments.setdefault(
                    key,
                    {
                        "scenario_id": sid,
                        "journey_id": witness["journey_id"],
                        "judgment": judgment["judgment"],
                        "reference_label": witness["journey_id"] in good,
                        "correct": correct,
                        "uses": [],
                    },
                )
                item["uses"].append(
                    {
                        "method": method,
                        "query": index + 1,
                        "removed_ids": [c.candidate_id for c in prefix_active if c not in after],
                        "model_final": classify(trajectory, good),
                        "oracle_final": classify(oracle[method]["4"], good),
                    }
                )
                prefix_active, used = after, used | {witness["journey_id"]}
            row["budgets"][method] = []
            for budget in BUDGETS:
                result = pair["outputs"][method][str(budget)]
                stop = state_at_budget(bundle, result, pool, budget)
                row["budgets"][method].append(stop)
                for mode, out in [("model", result), ("oracle", oracle[method][str(budget)])]:
                    budget_rows.append(
                        {
                            "scenario_id": sid,
                            "family": refs[sid]["family"],
                            "method": method,
                            "budget": budget,
                            "mode": mode,
                            "category": classify(out, good),
                            "correct": is_correct(classify(out, good)),
                            "reference_feasible": bool(good),
                            "judgments": len(out["judgments"]),
                            "plan_id": out["plan_id"],
                            "remaining": out.get("remaining_candidates", 0),
                            "calls": len(out["logical_calls"]),
                            "input_tokens": sum(
                                c.get("input_tokens") or 0 for c in out["logical_calls"]
                            ),
                            "output_tokens": sum(
                                c.get("output_tokens") or 0 for c in out["logical_calls"]
                            ),
                        }
                    )
        baseline = pair["secondary"]["A"]
        budget_rows.append(
            {
                "scenario_id": sid,
                "family": refs[sid]["family"],
                "method": "A",
                "budget": 0,
                "mode": "model",
                "category": classify(baseline, good),
                "correct": is_correct(classify(baseline, good)),
                "reference_feasible": bool(good),
                "judgments": 0,
                "plan_id": baseline["plan_id"],
                "calls": len(baseline["logical_calls"]),
                "input_tokens": sum(c.get("input_tokens") or 0 for c in baseline["logical_calls"]),
                "output_tokens": sum(
                    c.get("output_tokens") or 0 for c in baseline["logical_calls"]
                ),
            }
        )
        row["trajectory_differs"] = row["sequences"]["D"] != row["sequences"]["E"]
        if row["trajectory_differs"]:
            row["divergent_outputs"] = {}
            for mode, outputs in [("model", pair["outputs"]), ("oracle", oracle)]:
                row["divergent_outputs"][mode] = {}
                for method in "DE":
                    final = outputs[method]["4"]
                    selected = next(j for j in pool if j.journey_id == final["plan_id"])
                    row["divergent_outputs"][mode][method] = {
                        "plan_id": final["plan_id"],
                        "category": classify(final, good),
                        "formula": final.get("final_formula"),
                        "witnesses": final["witnesses"],
                        "judgments": final["judgments"],
                        "events": final["events"],
                        "repairs": final["repairs"],
                        "relative_arrival_vs_D_seconds": selected.rides[-1].arrival
                        - next(j for j in pool if j.journey_id == outputs["D"]["4"]["plan_id"])
                        .rides[-1]
                        .arrival,
                    }
        final = pair["outputs"]["D"]["4"]
        if not is_correct(classify(final, good)):
            failure = {
                "scenario_id": sid,
                "request": scenario.request,
                "reference": reference,
                "family": refs[sid]["family"],
                "all_raw_interpretations": parsed,
                "final_formula": final.get("final_formula"),
                "final_plan_id": final["plan_id"],
                "model_category": classify(final, good),
                "oracle_category": classify(oracle["D"]["4"], good),
                "reference_feasible_count": len(good),
                "reference_equivalent_ids": [
                    c.candidate_id
                    for c in active
                    if c.signature == tuple(j.journey_id in good for j in pool)
                ],
                "candidate_plan_correct_ids": [
                    c.candidate_id for c in active if c.plan.plan_id in good
                ],
                "violated_reference_clauses": [
                    rule
                    for rule in reference["and"]
                    if final["plan_id"]
                    and not check_reference(
                        rule, next(j for j in pool if j.journey_id == final["plan_id"])
                    )
                ],
                "annotation_check": "wording grammar agrees; provisional, no human audit",
                "repairs": final["repairs"],
            }
            failures.append(failure)
        # Source-only value sensitivity; never reuse a model verdict for an unasked witness.
        normalized = exact_candidates(normalized_exprs, pool)
        norm_bundle = {
            **deepcopy(bundle),
            "candidates": [c.record() for c in normalized],
            "initial_plan_id": normalized[0].plan.plan_id if normalized else None,
            "diagnostic": "posthoc_source_only_time_value_substitution",
        }
        norm_oracle = {m: oracle_prefixes(norm_bundle, pool, reference, m) for m in "DE"}
        try:
            a_expr = parse_interpretation(bundle["translations"][0], scenario)
            a_expr, _ = normalize_time_values(scenario.request, a_expr)
            a_c = exact_candidates([a_expr], pool)[0]
            a_out = {
                "status": a_c.plan.status,
                "plan_id": a_c.plan.plan_id,
                "candidates": [a_c.record()],
            }
        except InterpretationError:
            a_out = baseline
        normalization.append(
            {
                "scenario_id": sid,
                "source_mentions": time_mentions(scenario.request),
                "changed_atoms": sum(len(p.get("value_changes", [])) for p in parsed),
                "changed_interpretations": sum(bool(p.get("value_changes")) for p in parsed),
                "parsed_interpretations": parsed,
                "semantic_classes_after": len(normalized),
                "A_before": classify(baseline, good),
                "A_after_values_only": classify(a_out, good),
                "DE_initial_before": classify(pair["outputs"]["D"]["0"], good),
                "DE_initial_after_values_only": classify(norm_oracle["D"]["0"], good),
                "ordinary_final_replay": "not performed; changed witnesses lack saved ordinary judgments",
                "privileged_oracle_after_values_only": {
                    m: {
                        b: {
                            "category": classify(out, good),
                            "judgments": len(out["judgments"]),
                            "plan_id": out["plan_id"],
                        }
                        for b, out in outs.items()
                    }
                    for m, outs in norm_oracle.items()
                },
            }
        )
        expanded, expansion = network.pool(scenario.segments)
        assert expansion["complete"] and {j.journey_id for j in pool}.issubset(
            {j.journey_id for j in expanded}
        )
        broader = exact_candidates(exprs, expanded)
        vectors = Counter(tuple(c.signature[i] for c in broader) for i in range(len(expanded)))
        witness_partitions = {partition(v) for v in vectors if v and any(v) and not all(v)}
        same_pool_vectors = Counter(tuple(c.signature[i] for c in active) for i in range(len(pool)))
        union_parts = {partition(v) for v in same_pool_vectors if v and any(v) and not all(v)}
        exp_truth = tuple(check_reference(reference, j) for j in expanded)
        universe.append(
            {
                "scenario_id": sid,
                "family": refs[sid]["family"],
                "frozen_pool_size": len(pool),
                "expanded_pool_size": len(expanded),
                "expanded_pool_hash": digest([j.journey_id for j in expanded]),
                "expansion": expansion,
                "semantic_classes_before": len(active),
                "semantic_classes_after": len(broader),
                "witness_partitions_before": len(union_parts),
                "witness_partitions_after": len(witness_partitions),
                "expanded_initial_ranking": aggregate_ranking(broader, expanded),
                "reference_equivalent_before": any(
                    c.signature == tuple(j.journey_id in good for j in pool) for c in active
                ),
                "reference_equivalent_after": any(c.signature == exp_truth for c in broader),
                "reference_feasible_before": len(good),
                "reference_feasible_after": sum(exp_truth),
                "clauses_before": clause_effects(reference, pool),
                "clauses_after": clause_effects(reference, expanded),
                "modes": sorted({r.mode for j in expanded for r in j.rides}),
                "transfer_values_by_scope": {
                    s.scope: sorted(
                        {sum(r.scope == s.scope for r in j.rides) - 1 for j in expanded}
                    )
                    for s in scenario.segments
                },
                "expanded_candidate_plans": [
                    {
                        "candidate_id": c.candidate_id,
                        "status": c.plan.status,
                        "accepted": sum(c.signature),
                        "plan_id": c.plan.plan_id,
                        "correct_selected_plan": bool(c.plan.plan_id)
                        and check_reference(
                            reference, next(j for j in expanded if j.journey_id == c.plan.plan_id)
                        ),
                    }
                    for c in broader
                ],
            }
        )
        rows.append(row)
        print(f"CPU audit {sid}: pool {len(pool)} -> {len(expanded)}", flush=True)
    assert file_hash(ledger) == ledger_before
    artifacts = {
        "bundles": rows,
        "budget-outcomes": budget_rows,
        "failures": failures,
        "judgments": list(judgments.values()),
        "time-value-sensitivity": normalization,
        "pool-sensitivity": universe,
    }
    for name, data in artifacts.items():
        immutable_json(output / f"{name}.json", data)
    provenance = {
        "starting_revision": "06cefbc0eacf28350b3a3683cc1944b9ae9589a7",
        "source_run": str(run),
        "source_manifest_sha256": file_hash(run / "manifest.json"),
        "verified_raw_files": len(fixed["files"]),
        "ledger_sha256_before_and_after": ledger_before,
        "new_gpu_generations": 0,
        "new_gpu_seconds": 0,
        "reference_sha256": file_hash(references),
        "feed_sha256": file_hash(feed),
        "expanded_pool_config": expanded_config,
        "expansion_scope": "CPU-only uncapped sensitivity on same feed, routes, dates and two-ride bound; primary pools and outputs unchanged",
        "time_sensitivity_scope": "posthoc source-only AST value substitution; no new extraction generations; oracle branch explicitly privileged",
        "script_sha256": file_hash(Path(__file__)),
    }
    immutable_json(output / "provenance.json", provenance)
    return artifacts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, default=Path("runs/stage2-pilot-v1"))
    parser.add_argument("--public", type=Path, default=Path("data/prepared/stage2/public"))
    parser.add_argument("--references", type=Path, default=Path("data/pilot/references.json"))
    parser.add_argument("--config", type=Path, default=Path("configs/data.json"))
    parser.add_argument("--feed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.run, args.public, args.references, args.output, args.feed, read_json(args.config))


if __name__ == "__main__":
    main()
