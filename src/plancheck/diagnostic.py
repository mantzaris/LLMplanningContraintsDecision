"""Gold-label selection ablation, isolated from ordinary inference.

Run explicitly with python -m plancheck.diagnostic. Every artifact is labeled
injected/diagnostic; this never purports to be a language-model judgment experiment.
"""

from __future__ import annotations
import argparse
from pathlib import Path
from .constraints import ADAPTER
from .domain import Journey
from .reference import check_reference
from .selection import candidates, select_witness
from .util import canonical, immutable_json, read_json


def gold_selector_diagnostic(expressions, pool, reference, policy, limit=2):
    active = candidates(expressions, pool)
    history = []
    used = set()
    for _ in range(limit):
        witness = select_witness(active, pool, used, policy)
        if witness is None:
            break
        journey = next(j for j in pool if j.journey_id == witness["journey_id"])
        label = check_reference(reference, journey)
        used.add(journey.journey_id)
        active = [c for c in active if c.accepts(journey.journey_id) == label]
        history.append({"witness": witness, "gold_label": label})
    return {
        "mode": "gold_label_diagnostic",
        "error_source": "deliberately_injected",
        "history": history,
        "survivors": [c.candidate_id for c in active],
        "plan_id": active[0].plan.plan_id if active else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixture = read_json(args.fixture)
    pool = [Journey.model_validate_json(canonical(j)) for j in fixture["pool"]]
    expressions = [ADAPTER.validate_json(canonical(c)) for c in fixture["injected_candidates"]]
    immutable_json(
        args.output,
        {
            policy: gold_selector_diagnostic(expressions, pool, fixture["reference"], policy)
            for policy in ("balanced", "consequence")
        },
    )


if __name__ == "__main__":
    main()
