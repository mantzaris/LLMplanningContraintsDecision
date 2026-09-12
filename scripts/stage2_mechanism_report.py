#!/usr/bin/env python3
"""Render the fixed-pilot diagnosis and compact tables from preserved CPU audits."""

from __future__ import annotations
import argparse
from collections import Counter
import csv
from pathlib import Path

from plancheck.util import canonical, file_hash, immutable_json, read_json

# Assistant trace review, not human annotation. All case IDs are checked against the
# computed failure set before rendering. Numerical substitutions are in the audit JSON.
NOTES = {
    "pilot-01": (
        "Direction + numeric value; judge; missing useful candidate",
        "Latest departure became depart_ge, with wrong numbers. The wrong satisfied label keeps an invalid plan; oracle instead returns false infeasibility. Value-only binding cannot correct the operator.",
    ),
    "pilot-02": (
        "Wrong intermediate entities/order; missing alternatives",
        "All raw variants reject the pool because their visit requirements are wrong. Source timing normalization cannot fix the visit lists; oracle has no witness.",
    ),
    "pilot-05": (
        "Unsupported-model report",
        "All four outputs reject supported time operations. The requested same-day contradiction is intentional; no parsed AST exists for value-only repair.",
    ),
    "pilot-09": (
        "Numeric time encoding + one malformed JSON; missing alternatives",
        "09:39:47 is 34787 seconds, not 35947. The first output also contains a JSON comment. Three parsed copies agree on the wrong infeasible bound.",
    ),
    "pilot-14": (
        "Direction + numeric value; candidate elimination damage",
        "All variants turn a latest bound into an earliest bound. A correct negative witness label removes candidates with valid selected plans and leaves false infeasibility, including under oracle labels.",
    ),
    "pilot-15": (
        "Unsupported-model report",
        "All four outputs reject supported time operations; no parsed AST. The explicit 08:30 departure / 08:00 arrival contradiction is not a reference error.",
    ),
    "pilot-19": (
        "Reversed temporal inequality; missing alternatives",
        "The first value 28586 is correct for 07:56:26; other raw variants have wrong values. All use depart_ge instead of depart_le. One semantic class selects a late plan; value-only normalization cannot fix the direction.",
    ),
    "pilot-22": (
        "Invented outbound bound / scope + wrong return value",
        "Return-only wording is accompanied by an invented outbound bound, e.g. depart_ge 34500. Correcting the return value 32500 to 33900 leaves the added outbound restriction and false infeasibility.",
    ),
    "pilot-23": (
        "Unsupported-model report",
        "Four unsupported reports for supported time atoms; the deliberately infeasible conjunction remains representable. No parsed formula to normalize.",
    ),
    "pilot-27": (
        "Numeric time encoding; judge; missing useful candidate",
        "Return 09:40:00 is 34800 seconds; candidates use 35400 or 5840, among other values. A wrong positive label chooses a too-early return; oracle chooses false infeasibility. Value-only sensitivity recovers a valid initial plan.",
    ),
    "pilot-33": (
        "Unsupported-model report",
        "Four unsupported reports, not an infrastructure failure or proof of infeasibility. Clock conversion alone cannot recover a missing formula.",
    ),
    "pilot-34": (
        "Numeric time encoding; decisive judge error",
        "08:42:07 is 31327 seconds. The pool-equivalent c3 alternative exists despite its 31247 value; the second wrong label removes it. Correct oracle labels recover the request; value normalization also fixes the initial plan.",
    ),
    "pilot-35": (
        "Numeric time encoding; missing alternatives",
        "Return 09:16:00 is 33360 seconds; c0 uses 3696. Different formulas all accept the same pool and select an early return. Value-only sensitivity fixes the initial plan.",
    ),
    "pilot-40": (
        "Invented outbound bound / scope; decisive judge error",
        "A pool-equivalent, valid-plan alternative exists. The judge incorrectly says 09:42 is earlier than 09:12 and eliminates it. Normalizing the return number does not remove c0's invented outbound bound; correct oracle judgment is still needed.",
    ),
    "pilot-41": (
        "Unsupported-model report",
        "All four outputs incorrectly report supported departure/arrival operations unsupported. No AST exists; this is not an arithmetic compiler bug.",
    ),
}


def table(headers, rows):
    def clean(value):
        return str(value).replace("|", "\\|").replace("\n", " ")

    return "\n".join(
        ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
        + ["| " + " | ".join(clean(x) for x in row) + " |" for row in rows]
    )


def csv_write(path, rows):
    if not rows:
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            {k: canonical(v) if isinstance(v, (dict, list)) else v for k, v in row.items()}
            for row in rows
        )


def render(analysis: Path, report: Path):
    def load(name):
        return read_json(analysis / f"{name}.json")

    bundles, outcomes, failures = load("bundles"), load("budget-outcomes"), load("failures")
    times, pools, judgments = (
        load("time-value-sensitivity"),
        load("pool-sensitivity"),
        load("judgments"),
    )
    assert len(bundles) == 48 and {f["scenario_id"] for f in failures} == set(NOTES)

    def correct(category):
        return category in {"correct_feasible_plan", "correct_infeasibility"}

    primary = [r for r in outcomes if r["mode"] == "model" and r["method"] == "D"]
    by_budget = {
        b: {r["scenario_id"]: r for r in primary if r["budget"] == b} for b in (0, 1, 2, 4)
    }
    improved = [
        sid
        for sid in by_budget[0]
        if not by_budget[0][sid]["correct"] and by_budget[4][sid]["correct"]
    ]
    damaged = [
        sid
        for sid in by_budget[0]
        if by_budget[0][sid]["correct"] and not by_budget[4][sid]["correct"]
    ]
    always_wrong = [
        sid for sid in by_budget[0] if all(not by_budget[b][sid]["correct"] for b in (0, 1, 2, 4))
    ]
    summary = {
        "improved": improved,
        "damaged": damaged,
        "always_wrong": always_wrong,
        "exclusive_equivalence_causes": dict(
            Counter(r["exclusive_equivalence_cause"] for r in bundles)
        ),
        "new_gpu_generations": 0,
        "new_gpu_seconds": 0,
    }
    budget_table = []
    for method, budget in [("A", 0), ("D", 0), ("D", 1), ("D", 2), ("D", 4)]:
        rs = [
            r
            for r in outcomes
            if r["mode"] == "model" and r["method"] == method and r["budget"] == budget
        ]
        counts = Counter(r["category"] for r in rs)
        budget_table.append(
            [
                method if method == "A" else "D = E",
                budget,
                f"{sum(r['correct'] for r in rs)}/48",
                f"{counts['correct_feasible_plan']}/40",
                counts["incorrect_plan"],
                counts["false_infeasibility"],
                f"{counts['correct_infeasibility']}/8",
                counts["invalid_model_output"],
                counts["unresolved"],
                counts["solver_timeout"] + counts["infrastructure_failure"],
                sum(r["judgments"] for r in rs),
            ]
        )
    tokens = {
        "BUDGET_TABLE": table(
            [
                "Method",
                "Budget",
                "Correct",
                "Valid feasible",
                "Invalid plan",
                "False infeas.",
                "Correct infeas.",
                "Invalid output",
                "Unresolved",
                "Timeout/infra",
                "Judgments",
            ],
            budget_table,
        )
    }
    stop_rows = []
    for budget in (0, 1, 2, 4):
        counts = Counter(r["budgets"]["D"][(0, 1, 2, 4).index(budget)]["stop"] for r in bundles)
        stop_rows.append(
            [
                budget,
                counts["no_parsed_candidate"],
                counts["one_class_no_witness"],
                counts["judgment_budget_limit"],
            ]
        )
    tokens["STOP_TABLE"] = table(
        [
            "Budget",
            "No parsed candidate",
            "One class / no witness",
            "Budget cap with witnesses left",
        ],
        stop_rows,
    )
    tokens["EQUIVALENCE_TABLE"] = table(
        ["Mutually exclusive initial state", "Bundles", "Implication"],
        [
            [
                "No parsed interpretation",
                summary["exclusive_equivalence_causes"]["no_parsed_candidate"],
                "No selector operates",
            ],
            [
                "One semantic class",
                summary["exclusive_equivalence_causes"]["one_class"],
                "No witness",
            ],
            [
                "Two classes",
                summary["exclusive_equivalence_causes"]["two_classes"],
                "One pair / one cut partition",
            ],
            [
                "3+ classes, uniform weights",
                summary["exclusive_equivalence_causes"]["uniform_weights_3plus"],
                "E is a positive scalar multiple of D",
            ],
            [
                "Nonuniform, same first choice",
                summary["exclusive_equivalence_causes"]["variable_weights_same_first"],
                "pilot-06 and pilot-24; shared top-ID tie resolution",
            ],
            [
                "Nonuniform, different first choice",
                summary["exclusive_equivalence_causes"]["different_first"],
                "pilot-00 and pilot-37",
            ],
        ],
    )
    bundle_csv = []
    for r in bundles:
        s = r["initial_state"]
        bundle_csv.append(
            {
                "scenario_id": r["scenario_id"],
                "requested": r["requested"],
                "parsed": r["parsed"],
                "exact_duplicates": r["exact_text_duplicates"],
                "canonical_duplicates": r["canonical_duplicates"],
                "semantic_classes": r["semantic_classes"],
                "acceptance_patterns": s["patterns"],
                "weights": s["weights"],
                "witness_partitions": s["witness_partitions"],
                "D_ranking": s["ranks"]["D"],
                "E_ranking": s["ranks"]["E"],
                "D_top_ties": len(s["top_ids"]["D"]),
                "E_top_ties": len(s["top_ids"]["E"]),
                "D_sequence": r["sequences"]["D"],
                "E_sequence": r["sequences"]["E"],
                "D_stops": r["budgets"]["D"],
                "E_stops": r["budgets"]["E"],
                "exclusive_cause": r["exclusive_equivalence_cause"],
            }
        )
    csv_write(analysis / "all-bundles.csv", bundle_csv)
    failure_rows = []
    for failure in failures:
        sid = failure["scenario_id"]
        cause, note = NOTES[sid]
        failure_rows.append(
            {
                "scenario_id": sid,
                "ordinary": failure["model_category"],
                "oracle": failure["oracle_category"],
                "cause": cause,
                "trace_diagnosis": note,
                "reference_equivalent": bool(failure["reference_equivalent_ids"]),
                "annotation_uncertainty": "Provisional; grammar matches; human review absent. Arithmetic versus extraction cannot always be separated.",
            }
        )
    csv_write(analysis / "failure-taxonomy.csv", failure_rows)
    tokens["FAILURE_TABLE"] = table(
        ["Request", "Ordinary / oracle, budget 4", "Diagnosis"],
        [
            [r["scenario_id"], r["ordinary"] + " / " + r["oracle"], r["trace_diagnosis"]]
            for r in failure_rows
        ],
    )
    time_rows = []
    failure_ids = set(NOTES)
    for row in times:
        if row["scenario_id"] not in failure_ids or not row["source_mentions"]:
            continue
        values = sorted(
            {
                f"{a['scope']}:{a['op']}={a['value']}"
                for p in row["parsed_interpretations"]
                if "formula" in p
                for a in time_atoms(p["formula"])
            }
        )
        time_rows.append(
            [
                row["scenario_id"],
                "; ".join(m["text"] for m in row["source_mentions"]),
                "; ".join(values) or "No parsed AST",
                "; ".join(f"{m['scope']}:{m['op']}={m['seconds']}" for m in row["source_mentions"]),
                row["DE_initial_before"] + " → " + row["DE_initial_after_values_only"],
            ]
        )
    tokens["TIME_TABLE"] = table(
        [
            "Request",
            "Original timing text",
            "Predicted seconds atoms (all parsed variants)",
            "Independent source/reference seconds",
            "Value-only initial result",
        ],
        time_rows,
    )
    types = sorted({c["rule"]["requirement"] for p in pools for c in p["clauses_before"]})
    clauses = []
    for kind in types:
        before = Counter(
            c["effect"]
            for p in pools
            for c in p["clauses_before"]
            if c["rule"]["requirement"] == kind
        )
        after = Counter(
            c["effect"]
            for p in pools
            for c in p["clauses_after"]
            if c["rule"]["requirement"] == kind
        )
        clauses.append(
            [
                kind,
                sum(before.values()),
                before["always_true"],
                before["always_false"],
                before["varies"],
                after["always_true"],
                after["always_false"],
                after["varies"],
            ]
        )
    tokens["POOL_TABLE"] = table(
        [
            "Requirement",
            "Clauses",
            "Frozen always true",
            "Always false",
            "Varies",
            "Uncapped always true",
            "Always false",
            "Varies",
        ],
        clauses,
    )
    summary["expanded_pool_memberships"] = sum(p["expanded_pool_size"] for p in pools)
    summary["expanded_different_first_choices"] = [
        p["scenario_id"] for p in pools if p["expanded_initial_ranking"]["different_first_choice"]
    ]
    summary["expanded_weight_variation"] = [
        p["scenario_id"]
        for p in pools
        if len(p["expanded_initial_ranking"]["weight_histogram"]) > 1
    ]
    summary["pool_size_adds_classes"] = sum(
        p["semantic_classes_after"] > p["semantic_classes_before"] for p in pools
    )
    summary["pool_size_adds_partitions"] = sum(
        p["witness_partitions_after"] > p["witness_partitions_before"] for p in pools
    )
    summary["normalization"] = {
        m: {
            "before": sum(correct(r[m + "_before"]) for r in times),
            "after": sum(correct(r[m + "_after_values_only"]) for r in times),
        }
        for m in ("A", "DE_initial")
    }
    summary["normalization_oracle_final"] = {
        m: sum(correct(r["privileged_oracle_after_values_only"][m]["4"]["category"]) for r in times)
        for m in "DE"
    }
    wrong = [j for j in judgments if j["correct"] is False]
    assert len(wrong) == 7
    judge_notes = {
        (
            "pilot-01",
            1,
        ): "Both retain an invalid plan. Correct label changes it to false infeasibility; no correct resolution is available from the candidates.",
        (
            "pilot-06",
            1,
        ): "Both remove an alternative but keep the same valid selected plan; harmless to primary outcome.",
        (
            "pilot-06",
            2,
        ): "Both keep the same valid plan despite a second wrong label; no primary loss.",
        (
            "pilot-27",
            1,
        ): "Both switch false infeasibility to an invalid plan. Oracle remains falsely infeasible: no useful candidate-selected plan.",
        (
            "pilot-34",
            2,
        ): "Both eliminate the useful pool-equivalent candidate. Correcting this label after the identical first step recovers the request.",
        (
            "pilot-37",
            1,
        ): "E alone removes the equivalent candidate. Final plan is valid but arrives 6366 seconds later than D. Primary tie; objective harm.",
        (
            "pilot-40",
            1,
        ): "Both eliminate the valid alternative. Correcting the sole label recovers the request.",
    }
    tokens["JUDGMENT_TABLE"] = table(
        [
            "Request / query",
            "Journey ID",
            "Wrong verdict → reference",
            "Methods / downstream effect",
        ],
        [
            [
                j["scenario_id"] + "/" + str(j["uses"][0]["query"]),
                j["journey_id"],
                j["judgment"]["verdict"]
                + " → "
                + ("satisfied" if j["reference_label"] else "violated"),
                judge_notes[(j["scenario_id"], j["uses"][0]["query"])],
            ]
            for j in wrong
        ],
    )
    tokens["ALWAYS_WRONG"] = ", ".join(always_wrong)
    tokens["EXPANDED_DIVERGENCE"] = ", ".join(summary["expanded_different_first_choices"]) or "none"
    tokens["EXPANDED_VARIABLE_WEIGHTS"] = ", ".join(summary["expanded_weight_variation"]) or "none"
    # Retain all formulas, cuts, full rankings, judgments and updates for both divergent cases.
    immutable_json(
        analysis / "divergent-cases.json", [r for r in bundles if r["trajectory_differs"]]
    )
    immutable_json(analysis / "summary.json", summary)
    csv_write(analysis / "budget-outcomes.csv", outcomes)
    template = Path(__file__).with_suffix(".md").read_text()
    for name, value in tokens.items():
        template = template.replace("@" + name + "@", value)
    assert not __import__("re").search(r"@[A-Z_]+@", template)
    report.parent.mkdir(parents=True, exist_ok=True)
    if report.exists() and report.read_text() != template:
        raise ValueError("Report identity already exists with different content")
    report.write_text(template)
    immutable_json(
        analysis / "report-reproduction.json",
        {
            "renderer_sha256": file_hash(Path(__file__)),
            "template_sha256": file_hash(Path(__file__).with_suffix(".md")),
            "report_sha256": file_hash(report),
            "analysis_provenance_sha256": file_hash(analysis / "provenance.json"),
        },
    )
    print(summary)


def time_atoms(formula):
    if formula["kind"] == "atom":
        if formula["unit"] == "seconds":
            yield formula
    elif formula["kind"] == "all":
        for child in formula["children"]:
            yield from time_atoms(child)
    else:
        yield from time_atoms(formula["child"])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--analysis", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    render(a.analysis, a.report)
