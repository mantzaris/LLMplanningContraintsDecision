"""Offline manuscript analysis. Reads frozen runs; never invokes an inference backend."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from statistics import mean

from plancheck.domain import Journey
from plancheck.pilot_analysis import base_bootstrap, classify, is_correct, oracle_prefixes
from plancheck.reference import check_reference
from plancheck.selection import restore_candidates, rank_witnesses
from plancheck.util import file_hash

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "paper/icaart_position/analysis"
INPUTS: dict[str, str] = {}
NAMES = {"A": "Independent sampling", "B": "Diversified sampling", "C": "Solver-guided sampling"}


def read(path):
    path = ROOT / path
    INPUTS[str(path.relative_to(ROOT))] = file_hash(path)
    return json.loads(path.read_text())


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def table(name, rows):
    with (OUT / name).open("w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]), lineterminator="\n")
        w.writeheader()
        for row in rows:
            w.writerow(
                {
                    k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v
                    for k, v in row.items()
                }
            )


def dataset(stage):
    run = Path("runs") / ("stage2-pilot-v1" if stage == 2 else "stage3-fresh")
    refpath = "data/pilot/references.json" if stage == 2 else "data/sampling/references.json"
    refs = {r["scenario_id"]: r for r in read(refpath)}
    scenes = {s["scenario_id"]: s for s in read(run / "public-scenarios.json")}
    pools = {}
    for s in scenes.values():
        h = s["pool_hash"]
        if h not in pools:
            pools[h] = [
                Journey.model_validate_json(json.dumps(j))
                for j in read(run / "pools" / f"{h}.json")
            ]
    return run, refs, scenes, pools


def joint_counts(rows):
    """Joint cells from paired row observations, not marginal reconstruction."""
    return {
        f"G{g}S{s}": sum(r["G"] == bool(g) and r["S"] == bool(s) for r in rows)
        for g, s in [(1, 1), (1, 0), (0, 1), (0, 0)]
    }


def trace(output, reference_vector, pool):
    candidates = output["candidates"]
    active = list(candidates)
    ref = dict(zip([j.journey_id for j in pool], reference_vector))
    updates = []
    for record in output["judgments"]:
        jid, verdict = record["journey_id"], record["judgment"]["verdict"]
        before = [c["candidate_id"] for c in active]
        if verdict != "uncertain":
            active = [
                c
                for c in active
                if c["signature"][c["pool_ids"].index(jid)] == (verdict == "satisfied")
            ]
        updates.append(
            {
                "journey_id": jid,
                "judgment": record["judgment"],
                "reference_accepts": ref[jid],
                "before": before,
                "after": [c["candidate_id"] for c in active],
                "reference_candidates_after": [
                    c["candidate_id"] for c in active if c["signature"] == reference_vector
                ],
            }
        )
    ids = (
        {c["plan"]["plan_id"] for c in candidates}
        | {r["journey_id"] for r in output["judgments"]}
        | {output.get("plan_id")}
    )
    return {
        "candidates": [
            {k: v for k, v in c.items() if k not in {"pool_ids", "signature"}}
            | {
                "reference_equivalent": c["signature"] == reference_vector,
                "acceptance_bits": "".join(str(int(v)) for v in c["signature"]),
            }
            for c in candidates
        ],
        "journeys": [
            {
                "journey_id": j.journey_id,
                "rides": [
                    {
                        "route_id": r.route_id,
                        "scope": r.scope,
                        "calls": [r.calls[0].model_dump(), r.calls[-1].model_dump()],
                    }
                    for r in j.rides
                ],
            }
            for j in pool
            if j.journey_id in ids
        ],
        "witnesses": output["witnesses"],
        "updates": updates,
        "final_plan_id": output.get("plan_id"),
        "events": output["events"],
        "remaining_ids": [c["candidate_id"] for c in active],
    }


def verify_sources():
    verified = {}
    feed_hash = "82e6b822de008367b3d3d35bb52545807ea41b6f56623a9aa4b1162b3d54671b"
    feed = ROOT / f"data/raw/trimet-{feed_hash}.zip"
    # Replay needs saved pools, not the ZIP; verify the frozen source when present.
    if feed.exists():
        assert file_hash(feed) == feed_hash
        verified["local_frozen_feed_sha256"] = feed_hash
    for stage, path in [
        (2, "artifacts/stage2/pilot-v1/full-artifact-manifest.json"),
        (3, "artifacts/stage3/pilot-v1/input-checksums.json"),
    ]:
        manifest = read(path)
        files = manifest["files"] if stage == 2 else manifest
        run = ROOT / "runs" / ("stage2-pilot-v1" if stage == 2 else "stage3-fresh")
        for relative, record in files.items():
            expected = record["sha256"] if isinstance(record, dict) else record
            assert file_hash(run / relative) == expected, relative
        verified[f"stage{stage}_raw_files"] = len(files)
    storage = read("artifacts/stage3/pilot-v1/storage.json")
    for archive in storage["archives"]:
        assert file_hash(ROOT / archive["local_path"]) == archive["sha256"]
    verified["stage3_archives"] = storage["archives"]
    for name in [
        "configs/pilot.json",
        "configs/sampling.json",
        "data/pilot/protocol.json",
        "data/sampling/protocol.json",
    ]:
        read(name)
    verified["ledgers"] = {
        str(p.relative_to(ROOT)): file_hash(p)
        for p in sorted((ROOT / "runs").glob("stage*-gpu-budget.jsonl"))
    }
    save("verified-storage.json", verified)


def stage3():
    run, refs, scenes, pools = dataset(3)
    saved_oracles = read(run / "offline-oracle-stage3.json")
    rows, causes, examples, reviews = [], [], {}, []
    checks = {}
    for sid, scene in sorted(scenes.items()):
        pool = pools[scene["pool_hash"]]
        reference = refs[sid]["reference"]
        vector = [check_reference(reference, j) for j in pool]
        feasible = {j.journey_id for j, v in zip(pool, vector) if v}
        reviews.append(
            {
                "stage": 3,
                "scenario_id": sid,
                "request": scene["request"],
                "reference": reference,
                "pool_size": len(pool),
                "feasible_journeys": len(feasible),
                "annotation_status": "provisional; no independent human adjudication",
                "review_question": "Check time operator, inclusive boundary, scope and pool-relative infeasibility.",
                "reviewer_decision": "",
            }
        )
        pair = read(run / "pairs" / f"{sid}.json")
        for arm in "ABC":
            for checkpoint in [2, 4, 8]:
                output = pair["outputs"][arm][str(checkpoint)]
                assert all(
                    c["pool_ids"] == [j.journey_id for j in pool] for c in output["candidates"]
                )
                samples = output["samples"]
                assert len(samples) == checkpoint
                covered = any(s.get("signature") == vector for s in samples)
                outcome = classify(output, feasible)
                bundle = read(run / "bundles" / sid / f"{arm}-{checkpoint}.json")
                oracle = oracle_prefixes(bundle, pool, reference, "D", budgets=(0, 2))["2"]
                assert (
                    json.loads(json.dumps(oracle)) == saved_oracles[f"{sid}/{arm}/{checkpoint}"]
                ), (sid, arm, checkpoint)
                oracle_outcome = classify(oracle, feasible)
                calls = [s["call"] for s in samples] + output["logical_calls"]
                for judgment, call in zip(output["judgments"], output["logical_calls"]):
                    verdict = judgment["judgment"]["verdict"]
                    checks[call["key"]] = {
                        "scenario_id": sid,
                        "journey_id": judgment["journey_id"],
                        "verdict": verdict,
                        "reference_accepts": judgment["journey_id"] in feasible,
                        "wrong": verdict != "uncertain"
                        and (verdict == "satisfied") != (judgment["journey_id"] in feasible),
                    }
                attainable = any(
                    is_correct(classify(c["plan"], feasible)) for c in output["candidates"]
                )
                row = {
                    "scenario_id": sid,
                    "arm": arm,
                    "checkpoint": checkpoint,
                    "G": covered,
                    "S": is_correct(outcome),
                    "outcome": outcome,
                    "reference_feasible": bool(feasible),
                    "pool_size": len(pool),
                    "oracle_witness_correct": is_correct(oracle_outcome),
                    "oracle_witness_outcome": oracle_outcome,
                    "any_candidate_selected_plan_correct": attainable,
                    "candidate_count": len(output["candidates"]),
                    "parsed": sum(s["parse_status"] == "ok" for s in samples),
                    "logical_tokens": sum(c["charged_tokens"] for c in calls),
                    "logical_calls": len(calls),
                    "generation_tokens": sum(s["call"]["charged_tokens"] for s in samples),
                    "validation_tokens": output["validation_tokens"],
                    "judgments": len(output["judgments"]),
                    "final_plan_id": output.get("plan_id"),
                    "oracle_plan_id": oracle.get("plan_id"),
                }
                rows.append(row)
                if covered and not row["S"]:
                    t = trace(output, vector, pool)
                    matching = {
                        c["candidate_id"] for c in output["candidates"] if c["signature"] == vector
                    }
                    destructive = [
                        u
                        for u in t["updates"]
                        if matching.intersection(u["before"])
                        and not matching.intersection(u["after"])
                    ]
                    cause = (
                        "incorrect_judgment_eliminated_matching_candidate"
                        if destructive
                        else "requires_trace_review"
                    )
                    causes.append(
                        {
                            "scenario_id": sid,
                            "arm": arm,
                            "checkpoint": checkpoint,
                            "cause": cause,
                            "matching_candidate_ids": sorted(matching),
                            "destructive_updates": destructive,
                            "ordinary": t,
                            "oracle": trace(oracle, vector, pool),
                        }
                    )
                if checkpoint == 8 and (sid, arm) in {("sampling-12", "B"), ("sampling-20", "A")}:
                    examples[sid] = {
                        "request": scene["request"],
                        "reference": reference,
                        "stops": scene["stops"],
                        "arm": arm,
                        "row": row,
                        "ordinary": trace(output, vector, pool),
                        "oracle": trace(oracle, vector, pool),
                    }
    summary = []
    for arm in "ABC":
        for k in [2, 4, 8]:
            r = [r for r in rows if r["arm"] == arm and r["checkpoint"] == k]
            summary.append(
                {
                    "arm": arm,
                    "method": NAMES[arm],
                    "checkpoint": k,
                    "n": len(r),
                    **joint_counts(r),
                    **{
                        key: sum(x[key] for x in r)
                        for key in [
                            "G",
                            "S",
                            "oracle_witness_correct",
                            "any_candidate_selected_plan_correct",
                            "logical_tokens",
                            "generation_tokens",
                            "validation_tokens",
                            "logical_calls",
                            "judgments",
                        ]
                    },
                    "outcomes": dict(Counter(x["outcome"] for x in r)),
                }
            )
    comparisons = []
    for left, right in [("A", "B"), ("C", "A"), ("C", "B")]:
        for k in [2, 4, 8]:
            indexed = {(r["scenario_id"], r["arm"]): r for r in rows if r["checkpoint"] == k}
            for metric in ["G", "S"]:
                delta = {
                    sid: [int(indexed[sid, left][metric]) - int(indexed[sid, right][metric])]
                    for sid in sorted(scenes)
                }
                values = [d[0] for d in delta.values()]
                comparisons.append(
                    {
                        "left": left,
                        "right": right,
                        "checkpoint": k,
                        "metric": metric,
                        "wins": values.count(1),
                        "ties": values.count(0),
                        "losses": values.count(-1),
                        "difference": mean(values),
                        "base_bootstrap_95": base_bootstrap(delta, seed=31001),
                        "win_ids": [sid for sid, d in delta.items() if d[0] == 1],
                        "loss_ids": [sid for sid, d in delta.items() if d[0] == -1],
                    }
                )
    table("stage3-requests.csv", rows)
    table("stage3-joint.csv", summary)
    table("stage3-paired.csv", comparisons)
    save(
        "stage3-summary.json",
        {
            "checkpoints": summary,
            "paired": comparisons,
            "judgments": list(checks.values()),
            "token_overhead_final_C_over_A": summary[8]["logical_tokens"]
            / summary[2]["logical_tokens"]
            - 1,
            "token_overhead_final_C_over_B": summary[8]["logical_tokens"]
            / summary[5]["logical_tokens"]
            - 1,
        },
    )
    save("selection-failures.json", causes)
    save("worked-examples.json", examples)
    return reviews


def stage2():
    run, refs, scenes, pools = dataset(2)
    mechanism = {r["scenario_id"]: r for r in read("artifacts/stage2/mechanism-v1/bundles.json")}
    coverage = read("artifacts/stage2/closeout-v1/coverage.json")
    rows, reviews, opportunity = [], [], []
    for sid, scene in sorted(scenes.items()):
        pool = pools[scene["pool_hash"]]
        reference = refs[sid]["reference"]
        feasible = {j.journey_id for j in pool if check_reference(reference, j)}
        reviews.append(
            {
                "stage": 2,
                "scenario_id": sid,
                "request": scene["request"],
                "reference": reference,
                "pool_size": len(pool),
                "feasible_journeys": len(feasible),
                "annotation_status": "provisional; developer/automated audit found no clear correction",
                "review_question": "Check requested meaning separately from whether pool distinguishes it.",
                "reviewer_decision": "",
            }
        )
        pair = read(run / "pairs" / f"{sid}-r0.json")
        bundle = read(run / "bundles" / f"{sid}-r0.json")
        profile = mechanism[sid]
        candidates = restore_candidates(bundle["candidates"])
        for method, policy in [("D", "balanced"), ("E", "consequence")]:
            rank = rank_witnesses(candidates, pool, set(), policy)
            assert [
                {k: w[k] for k in ["cost", "journey_id", "score_numerator"]} for w in rank
            ] == profile["initial_state"]["ranks"][method]
            oracle = oracle_prefixes(bundle, pool, reference, method)
            for k in [0, 1, 2, 4]:
                output = pair["outputs"][method][str(k)]
                outcome = classify(output, feasible)
                rows.append(
                    {
                        "scenario_id": sid,
                        "method": method,
                        "budget": k,
                        "S": is_correct(outcome),
                        "outcome": outcome,
                        "reference_feasible": bool(feasible),
                        "oracle_witness_correct": is_correct(classify(oracle[str(k)], feasible)),
                        "judgments": len(output["judgments"]),
                        "final_plan_id": output.get("plan_id"),
                        "stop": next(
                            x["stop"] for x in profile["budgets"][method] if x["budget"] == k
                        ),
                    }
                )
        state = profile["initial_state"]
        opportunity.append(
            {
                "scenario_id": sid,
                "distinguishable": bool(state["witness_count"]),
                "consequential": any(w["I"] > 0 for w in state["weights"]),
                "uniform_weights": state["constant_weights"],
                "divergent_sequences": profile["trajectory_differs"],
                "semantic_classes": profile["semantic_classes"],
                "cause": profile["exclusive_equivalence_cause"],
            }
        )
    table("stage2-requests.csv", rows)
    table("stage2-opportunity.csv", opportunity)
    assert all(not r["divergent_sequences"] or r["consequential"] for r in opportunity)
    assert all(not r["consequential"] or r["distinguishable"] for r in opportunity)
    summary = {
        "n": len(scenes),
        "opportunity": {
            k: sum(r[k] for r in opportunity)
            for k in ["distinguishable", "consequential", "divergent_sequences"]
        },
        "uniform_among_consequential": sum(
            r["uniform_weights"] and r["consequential"] for r in opportunity
        ),
        "budgets": [
            {
                "method": method,
                "budget": k,
                "correct": sum(r["S"] for r in rows if r["method"] == method and r["budget"] == k),
                "oracle_correct": sum(
                    r["oracle_witness_correct"]
                    for r in rows
                    if r["method"] == method and r["budget"] == k
                ),
                "outcomes": dict(
                    Counter(
                        r["outcome"] for r in rows if r["method"] == method and r["budget"] == k
                    )
                ),
            }
            for method in "DE"
            for k in [0, 1, 2, 4]
        ],
        "clause_coverage": {
            family: dict(
                Counter(
                    c["effect"] for c in coverage["clauses"] if c["rule"]["requirement"] == family
                )
            )
            for family in sorted({c["rule"]["requirement"] for c in coverage["clauses"]})
        },
    }
    save("stage2-summary.json", summary)
    return reviews


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    verify_sources()
    reviews = stage2() + stage3()
    table("annotation-review.csv", reviews)
    costs()
    for path in [
        Path(__file__),
        ROOT / "src/plancheck/reference.py",
        ROOT / "src/plancheck/selection.py",
        ROOT / "src/plancheck/pilot_analysis.py",
    ]:
        INPUTS[str(path.relative_to(ROOT))] = file_hash(path)
    save("input-manifest.json", INPUTS)
    print(
        "Verified original storage checksums; reproduced 288 Stage 3 oracle prefixes and Stage 2 rankings; wrote request-level analyses."
    )


def costs():
    """Recompute resource statements from events and retained per-prefix charges."""
    path = ROOT / "runs/stage3-fresh/calls.jsonl"
    INPUTS[str(path.relative_to(ROOT))] = file_hash(path)
    events = [json.loads(line) for line in path.read_text().splitlines()]
    actual = [e["response"] for e in events if e["event"] == "generation_success"]
    ledgers = {}
    for stage in [1, 2, 3]:
        path = ROOT / f"runs/stage{stage}-gpu-budget.jsonl"
        INPUTS[str(path.relative_to(ROOT))] = file_hash(path)
        records = [json.loads(line) for line in path.read_text().splitlines()]
        ledgers[str(stage)] = {
            "calls": sum(e["event"] == "request_start" for e in records),
            "measured_seconds": sum(
                e["elapsed_seconds"] for e in records if e["event"] == "session_end"
            ),
        }
    rows = list(csv.DictReader((OUT / "stage3-requests.csv").open()))
    logical_tokens = sum(int(r["generation_tokens"]) for r in rows if r["checkpoint"] == "8") + sum(
        int(r["validation_tokens"]) for r in rows
    )
    logical_calls = 32 * 3 * 8 + sum(int(r["judgments"]) for r in rows)
    actual_tokens = sum(r["input_tokens"] + r["output_tokens"] for r in actual)
    assert (len(actual), actual_tokens, logical_calls, logical_tokens) == (
        659,
        1743059,
        833,
        2081931,
    )
    assert [ledgers[str(s)]["calls"] for s in [1, 2, 3]] == [46, 358, 683]
    read("data/sampling/automated-review.json")
    read("data/sampling/data-manifest.json")
    read("artifacts/stage2/mechanism-v1/summary.json")
    save(
        "costs.json",
        {
            "stage_ledgers": ledgers,
            "new_experimental_inference_calls": 0,
            "actual_fresh_calls": len(actual),
            "actual_fresh_tokens": actual_tokens,
            "logical_all_prefix_calls": logical_calls,
            "logical_all_prefix_tokens": logical_tokens,
            "tokens_saved_by_cache": logical_tokens - actual_tokens,
            "calls_saved_by_cache": logical_calls - len(actual),
            "historical_uncertainty_seconds": {"1": 30, "2": 30, "3": 60},
        },
    )


if __name__ == "__main__":
    main()
