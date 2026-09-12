"""Offline evaluation is an explicit separate command with reference access."""

from __future__ import annotations
import random
from pathlib import Path
from .domain import Journey
from .constraints import ADAPTER
from .compiler import predicate
from .reference import evaluate, check_reference
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
        reference = references[output["scenario_id"]]["reference"]
        gold_vector = [check_reference(reference, journey) for journey in pool]
        initial_formula = output["candidates"][0]["formula"] if output["candidates"] else None
        final_formula = output.get("final_formula")

        def equivalent(formula):
            if formula is None:
                return None
            expression = ADAPTER.validate_json(canonical(formula))
            return [predicate(expression, journey) for journey in pool] == gold_vector

        initial_equivalent = equivalent(initial_formula)
        final_equivalent = equivalent(final_formula)
        results.append(
            {
                "scenario_id": output["scenario_id"],
                "base_id": output["base_id"],
                "method": output["method"],
                **evaluate(reference, pool, output),
                "initial_interpretation_pool_equivalent": initial_equivalent,
                "final_interpretation_pool_equivalent": final_equivalent,
                "repair_damaged_correct_interpretation": bool(output["repairs"])
                and initial_equivalent is True
                and final_equivalent is not True,
                "candidate_pool_equivalence": [
                    equivalent(c["formula"]) for c in output["candidates"]
                ],
                "constraint_review_flags": constraint_review_flags(reference, final_formula),
                "judgment_checks": [
                    {
                        "journey_id": item["journey_id"],
                        "model_verdict": item["judgment"]["verdict"],
                        "reference_label": check_reference(
                            reference, next(j for j in pool if j.journey_id == item["journey_id"])
                        ),
                        "matches_reference": None
                        if item["judgment"]["verdict"] == "uncertain"
                        else (item["judgment"]["verdict"] == "satisfied")
                        == check_reference(
                            reference, next(j for j in pool if j.journey_id == item["journey_id"])
                        ),
                    }
                    for item in output["judgments"]
                ],
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


def constraint_review_flags(reference: dict, formula: dict | None) -> list[str]:
    """Structural triage only; equivalent reformulations may also trigger flags."""
    if formula is None:
        return ["no_final_interpretation"]
    mapping = {
        "latest_arrival": "arrive_by",
        "earliest_departure": "depart_ge",
        "latest_departure": "depart_le",
        "transfer_limit": "max_transfers",
        "allowed_modes": "permit_modes",
        "forbidden_modes": "exclude_modes",
        "ordered_calls": "visits",
    }

    def reference_atoms(node, negated=False):
        if "and" in node:
            return [a for child in node["and"] for a in reference_atoms(child, negated)]
        if "negate" in node:
            return reference_atoms(node["negate"], not negated)
        return [
            (mapping[node["requirement"]], node["direction"], canonical(node["target"]), negated)
        ]

    def predicted_atoms(node, negated=False):
        if node["kind"] == "all":
            return [a for child in node["children"] for a in predicted_atoms(child, negated)]
        if node["kind"] == "not":
            return predicted_atoms(node["child"], not negated)
        return [(node["op"], node["scope"], canonical(node["value"]), negated)]

    gold, predicted = set(reference_atoms(reference)), set(predicted_atoms(formula))
    flags = set()
    for op, scope, value, negated in gold ^ predicted:
        same_op = [
            a for a in (predicted if (op, scope, value, negated) in gold else gold) if a[0] == op
        ]
        if not same_op:
            flags.add("omitted_or_added_requirement")
        if any(a[1] != scope for a in same_op):
            flags.add("scope")
        if any(a[3] != negated for a in same_op):
            flags.add("negation")
        flags.add(
            "timing"
            if op in {"arrive_by", "depart_ge", "depart_le"}
            else "transfers"
            if op == "max_transfers"
            else "visits"
            if op == "visits"
            else "mode"
        )
    return sorted(flags)


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
