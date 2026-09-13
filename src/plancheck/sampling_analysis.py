"""Offline Stage 3 evaluation, oracle replay and compact reproducible figures.

References enter here only, never in sampling_run/semantic_sampling.
"""

from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
from statistics import mean
from .budget import Journal
from .domain import Journey
from .pilot_analysis import classify, is_correct, oracle_prefixes, base_bootstrap
from .reference import check_reference
from .util import read_json, immutable_json, file_hash, digest


def analyze(run: Path, references: Path, destination: Path):
    manifest = read_json(run / "manifest.json")
    cfg = manifest["config"]
    refs = {r["scenario_id"]: r["reference"] for r in read_json(references)}
    pools = {
        p.stem: [Journey.model_validate_json(__import__("json").dumps(j)) for j in read_json(p)]
        for p in (run / "pools").glob("*.json")
    }
    scenarios = {s["scenario_id"]: s for s in read_json(run / "public-scenarios.json")}
    rows = []
    trajectories = []
    oracle_records = {}
    heatmaps = {}
    checks = {}
    for sid in cfg["scenario_ids"]:
        pool = pools[scenarios[sid]["pool_hash"]]
        reference = refs[sid]
        refvector = [check_reference(reference, j) for j in pool]
        feasible = {j.journey_id for j, v in zip(pool, refvector) if v}
        pairpath = run / "pairs" / f"{sid}.json"
        pair = read_json(pairpath) if pairpath.exists() else None
        heatmaps[sid] = {
            "request": scenarios[sid]["request"],
            "journey_ids": [j.journey_id for j in pool],
            "reference": refvector,
            "arms": {},
        }
        for arm in "ABC":
            trajectory = read_json(run / "trajectories" / f"{sid}-{arm}.json")
            samples = trajectory["samples"]
            cumulative = 0
            discovered = False
            for s in samples:
                cumulative += s["call"]["charged_tokens"]
                discovered |= s.get("signature") == refvector
                trajectories.append(
                    {
                        "scenario_id": sid,
                        "arm": arm,
                        "attempt": s["index"],
                        "generation_tokens": cumulative,
                        "covered": discovered,
                        "valid": s["parse_status"] == "ok",
                        "signature_hash": s.get("signature_hash"),
                        "normalized": bool(s.get("normalization")),
                    }
                )
            heatmaps[sid]["arms"][arm] = [
                {
                    "attempt": s["index"],
                    "signature": s.get("signature"),
                    "formula": s.get("formula"),
                    "clauses": s.get("clauses"),
                    "parse_status": s["parse_status"],
                }
                for s in samples
            ]
            for checkpoint in cfg["checkpoints"]:
                prefix = samples[:checkpoint]
                valid = [s for s in prefix if s.get("signature") is not None]
                covered = any(s["signature"] == refvector for s in valid)
                bundle = read_json(run / "bundles" / sid / f"{arm}-{checkpoint}.json")
                output = (
                    pair["outputs"][arm][str(checkpoint)]
                    if pair
                    else {"status": "infrastructure_failure", "plan_id": None}
                )
                category = classify(output, feasible) if pair else "infrastructure_failure"
                oracle = oracle_prefixes(bundle, pool, reference, "D", budgets=(0, 2))["2"]
                oracle_category = classify(oracle, feasible)
                oracle_records[f"{sid}/{arm}/{checkpoint}"] = oracle
                calls = [s["call"] for s in prefix] + output.get("logical_calls", [])
                for item, call in zip(output.get("judgments", []), output.get("logical_calls", [])):
                    label = item["judgment"]["verdict"]
                    truth = item["journey_id"] in feasible
                    checks[call["key"]] = {
                        "scenario_id": sid,
                        "journey_id": item["journey_id"],
                        "verdict": label,
                        "reference": truth,
                        "correct": None
                        if label == "uncertain"
                        else (label == "satisfied") == truth,
                    }
                initial = dict(
                    output,
                    plan_id=output.get("initial_plan_id"),
                    status=bundle["candidates"][0]["plan"]["status"]
                    if bundle["candidates"]
                    else output.get("status"),
                )
                initial_correct = is_correct(classify(initial, feasible))
                correct = is_correct(category)
                full = len({tuple(s["signature"]) for s in valid})
                clauses = [c for s in valid for c in s["clauses"]]
                clause_keys = {
                    (digest(c["source_association"]), c["signature_hash"]) for c in clauses
                }
                failure = (
                    "correct"
                    if correct
                    else "missing_reference_equivalent_candidate"
                    if valid and not covered
                    else "selection_failure_with_reference_equivalent_candidate"
                    if covered
                    else "other_no_valid_candidate_or_execution"
                )
                rows.append(
                    {
                        "scenario_id": sid,
                        "arm": arm,
                        "checkpoint": checkpoint,
                        "attempts": len(prefix),
                        "parsed": len(valid),
                        "invalid": len(prefix) - len(valid),
                        "distinct_signatures": full,
                        "exact_duplicates": len(valid) - len({s["syntax_key"] for s in valid}),
                        "behavior_duplicates": len(valid) - full,
                        "clause_signatures": len(clause_keys),
                        "clauses_with_association": sum(
                            c["source_association"] is not None for c in clauses
                        ),
                        "clauses_without_association": sum(
                            c["source_association"] is None for c in clauses
                        ),
                        "covered": covered,
                        "correct": correct,
                        "outcome": category,
                        "reference_feasible": bool(feasible),
                        "oracle_correct": is_correct(oracle_category),
                        "oracle_outcome": oracle_category,
                        "correct_without_equivalent_candidate": correct and not covered,
                        "initial_correct": initial_correct,
                        "validation_improved": correct and not initial_correct,
                        "validation_damaged": initial_correct and not correct,
                        "failure": failure,
                        "generation_tokens": sum(s["call"]["charged_tokens"] for s in prefix),
                        "validation_tokens": output.get("validation_tokens", 0),
                        "logical_tokens": sum(c["charged_tokens"] for c in calls),
                        "logical_input_tokens": sum(c["input_tokens"] for c in calls),
                        "logical_output_tokens": sum(c.get("output_tokens") or 0 for c in calls),
                        "logical_calls": len(calls),
                        "logical_latency_seconds": sum(c.get("latency_seconds", 0) for c in calls),
                        "solver_seconds": sum(
                            c["plan"]["solver_seconds"] for c in bundle["candidates"]
                        ),
                        "judgments": len(output.get("judgments", [])),
                        "generation_stop": trajectory["stop"],
                        "validation_events": output.get("events", []),
                        "final_plan_id": output.get("plan_id"),
                    }
                )
    summary = {}
    paired = {}
    for checkpoint in cfg["checkpoints"]:
        for arm in "ABC":
            subset = [r for r in rows if r["arm"] == arm and r["checkpoint"] == checkpoint]
            summary[f"{arm}/{checkpoint}"] = {
                "n": len(subset),
                **{
                    k: sum(r[k] for r in subset)
                    for k in (
                        "covered",
                        "correct",
                        "oracle_correct",
                        "invalid",
                        "parsed",
                        "attempts",
                        "exact_duplicates",
                        "behavior_duplicates",
                        "correct_without_equivalent_candidate",
                        "validation_improved",
                        "validation_damaged",
                        "judgments",
                        "logical_input_tokens",
                        "logical_output_tokens",
                        "logical_tokens",
                        "logical_calls",
                        "generation_tokens",
                        "validation_tokens",
                        "solver_seconds",
                    )
                },
                "outcomes": dict(Counter(r["outcome"] for r in subset)),
                "mean_distinct_signatures": mean(r["distinct_signatures"] for r in subset),
                "mean_clause_signatures": mean(r["clause_signatures"] for r in subset),
                "mean_generation_tokens": mean(r["generation_tokens"] for r in subset),
                "mean_logical_tokens": mean(r["logical_tokens"] for r in subset),
                "mean_logical_latency_seconds": mean(r["logical_latency_seconds"] for r in subset),
                "generation_token_exhaustion": sum(
                    r["generation_stop"] == "generation_token_exhaustion" for r in subset
                ),
                "validation_token_exhaustion": sum(
                    "validation_token_exhaustion" in r["validation_events"] for r in subset
                ),
            }
        for baseline in "AB":
            for metric in ("covered", "correct"):
                indexed = {
                    (r["scenario_id"], r["arm"]): r for r in rows if r["checkpoint"] == checkpoint
                }
                deltas = {
                    sid: [int(indexed[sid, "C"][metric]) - int(indexed[sid, baseline][metric])]
                    for sid in cfg["scenario_ids"]
                }
                values = [v[0] for v in deltas.values()]
                paired[f"C-{baseline}/{checkpoint}/{metric}"] = {
                    "wins": values.count(1),
                    "ties": values.count(0),
                    "losses": values.count(-1),
                    "difference": mean(values),
                    "base_bootstrap_95_interval": base_bootstrap(deltas, seed=31001),
                }
    events = Journal(run / "calls.jsonl").read()
    actual = [e["response"] for e in events if e["event"] == "generation_success"]
    ledger = Journal(run.parent / "stage3-gpu-budget.jsonl").read()
    last = max(cfg["checkpoints"])
    final = [r for r in rows if r["checkpoint"] == last]
    selected = []
    for predicate in (
        lambda s: s["C"]["covered"] and not s["A"]["covered"] and not s["B"]["covered"],
        lambda s: not s["C"]["correct"],
        lambda s: len({(v["covered"], v["correct"]) for v in s.values()}) == 1,
    ):
        for sid in cfg["scenario_ids"]:
            by = {r["arm"]: r for r in final if r["scenario_id"] == sid}
            if predicate(by):
                selected.append(sid)
                break
    selected = list(dict.fromkeys(selected or cfg["scenario_ids"][:1]))
    result = {
        "run_revision": manifest["repository_revision"],
        "config_hash": manifest["config_hash"],
        "n": len(cfg["scenario_ids"]),
        "summary": summary,
        "paired": paired,
        "continuation_met": all(
            paired[f"C-{b}/{last}/covered"]["difference"] >= 0.10
            and paired[f"C-{b}/{last}/correct"]["difference"] >= 0.05
            for b in "AB"
        ),
        "actual_fresh_calls": sum(e["event"] == "generation_start" for e in events),
        "actual_fresh_failed_calls": sum(e["event"] == "generation_error" for e in events),
        "actual_fresh_input_tokens": sum(r["input_tokens"] for r in actual),
        "actual_fresh_output_tokens": sum(r["output_tokens"] for r in actual),
        "actual_fresh_inference_seconds": sum(r["latency_seconds"] for r in actual),
        "stage_calls": sum(e["event"] == "request_start" for e in ledger),
        "stage_measured_gpu_seconds": sum(
            e["elapsed_seconds"] for e in ledger if e["event"] == "session_end"
        ),
        "stage_sessions": sum(e["event"] == "session_start" for e in ledger),
        "distinct_judgments": len(checks),
        "wrong_distinct_judgments": sum(v["correct"] is False for v in checks.values()),
        "uncertain_distinct_judgments": sum(v["correct"] is None for v in checks.values()),
        "illustrative_ids": selected,
        "reference_file_hash": file_hash(references),
    }
    immutable_json(destination / "summary.json", result)
    immutable_json(destination / "rows.json", rows)
    immutable_json(destination / "discovery.json", trajectories)
    immutable_json(destination / "judge-checks.json", checks)
    immutable_json(destination / "heatmaps.json", {sid: heatmaps[sid] for sid in selected})
    immutable_json(
        destination / "input-checksums.json",
        {str(p.relative_to(run)): file_hash(p) for p in sorted(run.rglob("*")) if p.is_file()},
    )
    immutable_json(run / "offline-oracle-stage3.json", oracle_records)
    figures(destination)
    return result


def figures(directory: Path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    result = read_json(directory / "summary.json")
    rows = read_json(directory / "rows.json")
    checkpoints = sorted({r["checkpoint"] for r in rows})
    colors = {"A": "#0072B2", "B": "#E69F00", "C": "#009E73"}
    plt.rcParams.update(
        {
            "font.size": 10,
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    out = directory / "figures"
    out.mkdir(exist_ok=True)

    def save(fig, name):
        fig.tight_layout()
        for ext in ("pdf", "svg", "png"):
            fig.savefig(out / f"{name}.{ext}", dpi=180, bbox_inches="tight")
        plt.close(fig)

    for metric, token, name, label in [
        ("covered", "mean_generation_tokens", "coverage", "Bounded correct-candidate coverage"),
        ("correct", "mean_logical_tokens", "correctness", "Ordinary final-plan correctness"),
    ]:
        fig, ax = plt.subplots(figsize=(6.3, 3.6))
        for arm in "ABC":
            data = [result["summary"][f"{arm}/{k}"] for k in checkpoints]
            ax.plot(
                [s[token] / 1000 for s in data],
                [s[metric] / s["n"] for s in data],
                "o-",
                label=arm,
                color=colors[arm],
            )
            for k, s in zip(checkpoints, data):
                ax.annotate(
                    str(k),
                    (s[token] / 1000, s[metric] / s["n"]),
                    xytext=(3, 5),
                    textcoords="offset points",
                    fontsize=8,
                )
        ax.set(xlabel="Mean consumed logical tokens (thousands)", ylabel=label, ylim=(0, 1.05))
        ax.legend(title="Sampling arm")
        ax.grid(alpha=0.2)
        ax.set_title(f"Exploratory development evidence: {result['n']} base requests")
        save(fig, name)
    maps = read_json(directory / "heatmaps.json")
    fig, axes = plt.subplots(len(maps), 1, figsize=(8, 3 * len(maps)), squeeze=False)
    for ax, (sid, data) in zip(axes.flat, maps.items()):
        vectors = [data["reference"]]
        labels = ["Reference (offline)"]
        for arm, samples in data["arms"].items():
            for s in samples:
                vectors.append(
                    s["signature"]
                    if s["signature"] is not None
                    else [np.nan] * len(data["reference"])
                )
                labels.append(f"{arm}{s['attempt']}")
        cmap = plt.get_cmap("Blues").copy()
        cmap.set_bad("#bdbdbd")
        ax.imshow(
            np.array(vectors, dtype=float),
            aspect="auto",
            interpolation="nearest",
            vmin=0,
            vmax=1,
            cmap=cmap,
        )
        ax.set_yticks(range(len(labels)), labels, fontsize=6)
        ax.set(
            xlabel="Journey index in fixed public pool",
            title=f"{sid}: white reject, blue accept, gray invalid",
        )
    save(fig, "behavior-heatmaps")
    final = [r for r in rows if r["checkpoint"] == max(checkpoints)]
    fig, ax = plt.subplots(figsize=(6.3, 3.7))
    bottom = np.zeros(3)
    for cat, col, label in [
        ("correct", "#009E73", "Correct output"),
        (
            "missing_reference_equivalent_candidate",
            "#D55E00",
            "Incorrect; missing reference-equivalent candidate",
        ),
        (
            "selection_failure_with_reference_equivalent_candidate",
            "#CC79A7",
            "Incorrect; reference-equivalent candidate available",
        ),
        ("other_no_valid_candidate_or_execution", "#999999", "Other / no valid candidate"),
    ]:
        heights = np.array(
            [sum(r["arm"] == a and r["failure"] == cat for r in final) for a in "ABC"]
        )
        ax.bar(list("ABC"), heights, bottom=bottom, color=col, label=label)
        bottom += heights
    ax.set(
        ylabel="Base requests",
        xlabel="Sampling arm",
        title="Final allowance: operational failure decomposition",
    )
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.18))
    save(fig, "failure-decomposition")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path)
    p.add_argument("--references", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--figures-only", action="store_true")
    a = p.parse_args()
    if a.figures_only:
        figures(a.output)
    else:
        print(analyze(a.run, a.references, a.output))
