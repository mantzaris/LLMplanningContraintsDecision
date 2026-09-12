"""Offline evaluation is an explicit separate command with reference access."""

from __future__ import annotations
import random
from pathlib import Path
from .domain import Journey
from .reference import evaluate
from .util import digest, immutable_json, read_json, canonical


def evaluate_run(run_dir: Path, references_path: Path) -> dict:
    references = {r["scenario_id"]: r for r in read_json(references_path)}
    scenarios = {r["scenario_id"]: r for r in read_json(run_dir / "public-scenarios.json")}
    results = []
    for path in sorted((run_dir / "outputs").glob("*.json")):
        output = read_json(path)
        scenario = scenarios[output["scenario_id"]]
        pool = [
            Journey.model_validate_json(canonical(j))
            for j in read_json(run_dir / "pools" / f"{scenario['pool_hash']}.json")
        ]
        results.append(
            {
                "scenario_id": output["scenario_id"],
                "base_id": output["base_id"],
                "method": output["method"],
                **evaluate(references[output["scenario_id"]]["reference"], pool, output),
            }
        )
    artifact = {
        "reference_hash": digest(list(references.values())),
        "status": "provisional_unaudited",
        "unit_of_independence": "base_id",
        "results": results,
    }
    immutable_json(run_dir / "evaluation.json", artifact)
    return artifact


def paired_interval(rows: list[dict], replicates: int = 2000, seed: int = 104):
    groups = {}
    for row in rows:
        groups.setdefault(row["base_id"], {}).setdefault(row["method"], []).append(
            int(row["complete_satisfaction"])
        )
    differences = []
    for methods in groups.values():
        if "D" in methods and "E" in methods:
            differences.append(
                sum(methods["E"]) / len(methods["E"]) - sum(methods["D"]) / len(methods["D"])
            )
    if len(differences) < 2:
        return {
            "base_groups": len(differences),
            "interval": None,
            "reason": "too few independent base groups",
        }
    rng = random.Random(seed)
    samples = sorted(
        sum(rng.choices(differences, k=len(differences))) / len(differences)
        for _ in range(replicates)
    )
    return {
        "base_groups": len(differences),
        "mean_E_minus_D": sum(differences) / len(differences),
        "bootstrap_95_percent": [
            samples[int(0.025 * replicates)],
            samples[int(0.975 * replicates)],
        ],
    }


def report(run_dir: Path, destination: Path) -> str:
    evaluation = read_json(run_dir / "evaluation.json")
    rows = evaluation["results"]
    outputs = [read_json(p) for p in sorted((run_dir / "outputs").glob("*.json"))]
    lines = [
        "# Development smoke evidence",
        "",
        "Provisional, unaudited reference annotations. No population performance claim.",
        "",
        "| Method | Requests | Satisfied plans | Invalid plans | Correct infeasibility | False infeasibility | Unresolved | Logical calls |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method in "ABCDE":
        selected = [r for r in rows if r["method"] == method]
        logical = sum(len(o["logical_calls"]) for o in outputs if o["method"] == method)
        lines.append(
            f"| {method} | {len(selected)} | "
            + " | ".join(
                str(sum(r[k] for r in selected))
                for k in (
                    "complete_satisfaction",
                    "invalid_plan_returned",
                    "correct_infeasibility",
                    "false_infeasibility",
                    "unresolved",
                )
            )
            + f" | {logical} |"
        )
    lines += ["", "Paired base-group uncertainty: `" + canonical(paired_interval(rows)) + "`.", ""]
    text = "\n".join(lines)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.read_text() != text:
        raise ValueError("Refusing to overwrite report from different evidence")
    destination.write_text(text)
    return text
