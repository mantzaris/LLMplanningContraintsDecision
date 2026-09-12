"""Frozen v1 weighted pair separation; balanced policy changes only pair weights."""

from __future__ import annotations
from dataclasses import asdict, dataclass
from fractions import Fraction
from itertools import combinations
from .compiler import PlanResult, predicate, solve
from .constraints import Expression, syntax_key
from .domain import Journey


@dataclass
class Candidate:
    candidate_id: str
    expression: Expression
    signature: tuple[bool, ...]
    pool_ids: tuple[str, ...]
    plan: PlanResult
    aliases: list[str]

    def record(self):
        return {
            "candidate_id": self.candidate_id,
            "formula": self.expression.model_dump(mode="json"),
            "signature": self.signature,
            "pool_ids": self.pool_ids,
            "plan": asdict(self.plan),
            "aliases": self.aliases,
        }

    def accepts(self, journey_id: str) -> bool:
        return self.signature[self.pool_ids.index(journey_id)]


def candidates(expressions: list[Expression], pool: list[Journey], timeout_ms: int = 5000):
    unique: list[Candidate] = []
    syntax = {}
    semantic = {}
    for index, expr in enumerate(expressions):
        alias = f"c{index}"
        key = syntax_key(expr)
        if key in syntax:
            syntax[key].aliases.append(alias)
            continue
        signature = tuple(predicate(expr, journey) for journey in pool)
        if signature in semantic:
            semantic[signature].aliases.append(alias)
            syntax[key] = semantic[signature]
            continue
        candidate = Candidate(
            alias,
            expr,
            signature,
            tuple(j.journey_id for j in pool),
            solve(expr, pool, timeout_ms),
            [alias],
        )
        syntax[key] = semantic[signature] = candidate
        unique.append(candidate)
    return unique


def consequence(left: Candidate, right: Candidate, indices: dict[str, int]) -> int:
    score = 0
    if left.plan.plan_id is not None:
        score += not right.accepts(left.plan.plan_id)
    if right.plan.plan_id is not None:
        score += not left.accepts(right.plan.plan_id)
    return int(score)


def select_witness(
    active: list[Candidate],
    pool: list[Journey],
    used: set[str],
    policy: str,
    costs: dict[str, int] | None = None,
) -> dict | None:
    if policy not in {"balanced", "consequence"}:
        raise ValueError(policy)
    indices = {j.journey_id: i for i, j in enumerate(pool)}
    pairs = [
        (left, right, consequence(left, right, indices)) for left, right in combinations(active, 2)
    ]
    options = []
    for index, journey in enumerate(pool):
        if journey.journey_id in used:
            continue
        separated = [
            (left.candidate_id, right.candidate_id, impact)
            for left, right, impact in pairs
            if left.accepts(journey.journey_id) != right.accepts(journey.journey_id)
        ]
        if not separated:
            continue
        cost = costs[journey.journey_id] if costs else 1
        if cost <= 0:
            raise ValueError("witness costs must be positive")
        numerator = sum(
            1 + (impact if policy == "consequence" else 0) for _, _, impact in separated
        )
        score = Fraction(numerator, cost)
        options.append(
            (
                score,
                journey.journey_id,
                {
                    "journey_id": journey.journey_id,
                    "policy": policy,
                    "score_numerator": numerator,
                    "cost": cost,
                    "score": float(score),
                    "separated_pairs": separated,
                },
            )
        )
    if not options:
        return None
    return sorted(options, key=lambda item: (-item[0], item[1]))[0][2]
