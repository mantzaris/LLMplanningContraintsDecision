"""Descriptive selection diagnostics; never used to select or filter pilot requests."""

from itertools import combinations
from collections import Counter
from .constraints import parse_interpretation, syntax_key, InterpretationError
from .selection import consequence, rank_witnesses, restore_candidates


def profile_bundle(bundle, scenario, pool):
    active = restore_candidates(bundle["candidates"])
    syntax = []
    for raw in bundle["translations"]:
        try:
            syntax.append(syntax_key(parse_interpretation(raw, scenario)))
        except InterpretationError:
            pass
    pairs = [
        {
            "left": a.candidate_id,
            "right": b.candidate_id,
            "impact": consequence(a, b, {}),
            "weight": 1 + consequence(a, b, {}),
            "different_selected_plans": a.plan.plan_id != b.plan.plan_id,
            "witness_count": sum(x != y for x, y in zip(a.signature, b.signature)),
        }
        for a, b in combinations(active, 2)
    ]
    rankings = {
        policy: rank_witnesses(active, pool, set(), policy)
        for policy in ("balanced", "consequence")
    }

    def top(policy):
        rows = rankings[policy]
        return {
            "chosen": rows[0] if rows else None,
            "top_tie_count": sum(r["score"] == rows[0]["score"] for r in rows) if rows else 0,
            "ranked_ids": [r["journey_id"] for r in rows],
        }

    return {
        "raw_candidates": len(bundle["translations"]),
        "valid_candidates": len(syntax),
        "syntactic_classes": len(set(syntax)),
        "semantic_classes": len(active),
        "distinct_journey_acceptance_patterns": len(
            {tuple(c.accepts(j.journey_id) for c in active) for j in pool}
        ),
        "pairs": pairs,
        "weight_histogram": dict(Counter(str(p["weight"]) for p in pairs)),
        "variable_weights": len({p["weight"] for p in pairs}) > 1,
        "candidate_plan_disagreements": sum(p["different_selected_plans"] for p in pairs),
        "witness_count": len(rankings["balanced"]),
        "balanced": top("balanced"),
        "consequence": top("consequence"),
        "different_choice": top("balanced")["chosen"] is not None
        and top("balanced")["chosen"]["journey_id"] != top("consequence")["chosen"]["journey_id"],
        "different_ranking": top("balanced")["ranked_ids"] != top("consequence")["ranked_ids"],
    }
