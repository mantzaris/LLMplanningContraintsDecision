"""Offline normalization and feedback diagnostics; never used to guide sampling."""

from pathlib import Path
import argparse
from collections import Counter
from plancheck.constraints import ADAPTER
from plancheck.compiler import predicate
from plancheck.domain import Journey
from plancheck.reference import check_reference
from plancheck.util import read_json, canonical, immutable_json


def main(run, references, output):
    refs = {r["scenario_id"]: r["reference"] for r in read_json(references)}
    scenarios = read_json(run / "public-scenarios.json")
    rows = []
    for scenario in scenarios:
        sid = scenario["scenario_id"]
        pool = [
            Journey.model_validate_json(canonical(j))
            for j in read_json(run / "pools" / f"{scenario['pool_hash']}.json")
        ]
        truth = [check_reference(refs[sid], j) for j in pool]
        for arm in "ABC":
            samples = read_json(run / "trajectories" / f"{sid}-{arm}.json")["samples"]
            raw = []
            for sample in samples:
                formula = sample.get("raw_formula")
                if formula is None:
                    raw.append(None)
                    continue
                expr = ADAPTER.validate_json(canonical(formula))
                raw.append([predicate(expr, j) for j in pool])
            full = [s.get("signature") for s in samples]
            initial = {tuple(v) for v in full[:2] if v is not None}
            later = {tuple(v) for v in full[2:] if v is not None} - initial
            row = {
                "scenario_id": sid,
                "arm": arm,
                "raw_coverage_at_2": truth in raw[:2],
                "normalized_coverage_at_2": truth in full[:2],
                "raw_coverage_final": truth in raw,
                "normalized_coverage_final": truth in full,
                "normalization_affected_attempts": sum(
                    bool(s.get("normalization")) for s in samples
                ),
                "normalization_changed_atoms": sum(
                    len(s.get("normalization", [])) for s in samples
                ),
                "new_signatures_after_shared_two": len(later),
                "new_correct_signature_after_shared_two": tuple(truth) in later,
                "new_nonreference_signatures_after_shared_two": sum(
                    v != tuple(truth) for v in later
                ),
                "full_reject_masks_varying_clause_attempts": sum(
                    v is not None
                    and not any(v)
                    and any(any(c["signature"]) and not all(c["signature"]) for c in s["clauses"])
                    for s, v in zip(samples, full)
                ),
                "unassociated_clauses": sum(
                    c["source_association"] is None for s in samples for c in s.get("clauses", [])
                ),
            }
            rows.append(row)
    aggregate = {
        a: dict(
            Counter(
                {
                    k: sum(r[k] for r in rows if r["arm"] == a)
                    for k in rows[0]
                    if k not in {"scenario_id", "arm"}
                }
            )
        )
        for a in "ABC"
    }
    immutable_json(
        output,
        {
            "rows": rows,
            "aggregate": aggregate,
            "mode": "offline privileged diagnostic; no new calls; normalization shared across arms",
        },
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--references", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    main(a.run, a.references, a.output)
