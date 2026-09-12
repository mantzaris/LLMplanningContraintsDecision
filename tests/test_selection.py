from itertools import combinations
from plancheck.selection import candidates, consequence, select_witness
from plancheck.compiler import predicate
from test_logic import atom


def test_dedup_witnesses_scores(pool):
    cs = candidates(
        [
            atom("arrive_by", 200),
            atom("arrive_by", 200),
            atom("arrive_by", 205),
            atom("depart_ge", 150),
            atom("max_transfers", 0, "count"),
        ],
        pool,
    )
    assert len(cs) == 3
    assert cs[0].aliases == ["c0", "c1", "c2"]
    indices = {j.journey_id: i for i, j in enumerate(pool)}
    for left, right in combinations(cs, 2):
        expected = int(
            not predicate(
                right.expression, next(j for j in pool if j.journey_id == left.plan.plan_id)
            )
        )
        expected += int(
            not predicate(
                left.expression, next(j for j in pool if j.journey_id == right.plan.plan_id)
            )
        )
        assert consequence(left, right, indices) == expected
    for policy in ("balanced", "consequence"):
        w = select_witness(cs, pool, set(), policy)
        j = next(j for j in pool if j.journey_id == w["journey_id"])
        by_id = {c.candidate_id: c for c in cs}
        assert w["score_numerator"] == sum(
            1 + (impact if policy == "consequence" else 0) for _, _, impact in w["separated_pairs"]
        )
        for left, right, _ in w["separated_pairs"]:
            assert predicate(by_id[left].expression, j) != predicate(by_id[right].expression, j)
        assert (
            select_witness(cs, list(reversed(pool)), set(), policy)["journey_id"] == w["journey_id"]
        )
    assert select_witness(cs, pool, {j.journey_id for j in pool}, "balanced") is None


def test_missing_plans_and_cost_tiebreak(pool):
    cs = candidates([atom("arrive_by", 0), atom("arrive_by", 200)], pool)
    assert consequence(*cs, {j.journey_id: i for i, j in enumerate(pool)}) == 1
    assert select_witness(cs, pool, set(), "consequence")["score"] == 2
    cs = candidates([atom("arrive_by", 0), atom("arrive_by", 400)], pool)
    assert select_witness(cs, pool, set(), "balanced")["journey_id"] == "a"
    costs = {j.journey_id: 2 if j.journey_id == "a" else 1 for j in pool}
    assert select_witness(cs, pool, set(), "balanced", costs)["journey_id"] == "b"
