"""Small exhaustive checks for the offline equivalence argument and value-only boundary."""

from fractions import Fraction
from importlib.util import module_from_spec, spec_from_file_location
from itertools import combinations, product
from pathlib import Path

from plancheck.compiler import PlanResult
from plancheck.constraints import Atom, All
from plancheck.domain import Call, Journey, Ride
from plancheck.selection import Candidate, rank_witnesses

spec = spec_from_file_location(
    "mechanism", Path(__file__).parents[1] / "scripts/stage2_mechanism_diagnosis.py"
)
mechanism = module_from_spec(spec)
spec.loader.exec_module(mechanism)


def test_exhaustive_cut_scores_and_equivalence_conditions():
    # All distinct candidate truth functions on three ordered journeys, 1..4 candidates.
    # Plans are independently selected as the first accepted journey, or missing if unsat.
    pool = [
        Journey(
            journey_id=str(i),
            rides=(
                Ride(
                    trip_id=str(i),
                    route_id="r",
                    mode="bus",
                    calls=(
                        Call(stop_id="a", arrival_s=i * 10, departure_s=i * 10),
                        Call(stop_id="b", arrival_s=i * 10 + 1, departure_s=i * 10 + 1),
                    ),
                ),
            ),
        )
        for i in range(3)
    ]
    atom = Atom(kind="atom", op="depart_ge", scope="outbound", value=0, unit="seconds")
    functions = list(product((False, True), repeat=3))
    checked = 0
    for n in range(1, 5):
        for vectors in combinations(functions, n):
            plans = [next((i for i, value in enumerate(v) if value), None) for v in vectors]
            cs = [
                Candidate(
                    str(k),
                    atom,
                    v,
                    ("0", "1", "2"),
                    PlanResult(
                        "satisfiable" if plans[k] is not None else "infeasible_in_pool",
                        str(plans[k]) if plans[k] is not None else None,
                        0,
                    ),
                    [str(k)],
                )
                for k, v in enumerate(vectors)
            ]
            impacts = {
                (a, b): int(plans[a] is not None and not vectors[b][plans[a]])
                + int(plans[b] is not None and not vectors[a][plans[b]])
                for a, b in combinations(range(n), 2)
            }
            partitions = {
                mechanism.partition(tuple(v[i] for v in vectors))
                for i in range(3)
                if any(v[i] for v in vectors) and not all(v[i] for v in vectors)
            }
            for costs in ({"0": 1, "1": 1, "2": 1}, {"0": 3, "1": 1, "2": 2}):
                rankings = {}
                for method, policy in [("D", "balanced"), ("E", "consequence")]:
                    expected = []
                    for i in range(3):
                        cut = [(a, b) for a, b in impacts if vectors[a][i] != vectors[b][i]]
                        if cut:
                            numerator = len(cut) + (
                                sum(impacts[p] for p in cut) if method == "E" else 0
                            )
                            expected.append((Fraction(numerator, costs[str(i)]), str(i)))
                    expected.sort(key=lambda x: (-x[0], x[1]))
                    rankings[method] = [
                        r["journey_id"] for r in rank_witnesses(cs, pool, set(), policy, costs)
                    ]
                    assert rankings[method] == [jid for _, jid in expected]
                    if set(costs.values()) == {1}:
                        # The expanded-pool audit groups patterns for speed. Verify its
                        # top score, full tie size and ID against the same exhaustive cut.
                        top = mechanism.aggregate_ranking(cs, pool)["top"][method]
                        assert top["chosen_id"] == (expected[0][1] if expected else None)
                        assert top["score"] == (expected[0][0] if expected else 0)
                        assert top["tie_count"] == sum(
                            score == expected[0][0] for score, _ in expected
                        )
                if n <= 2 or len(set(impacts.values())) <= 1 or len(partitions) <= 1:
                    assert rankings["D"] == rankings["E"]
                checked += 1
    assert checked == 324


def test_time_value_sensitivity_cannot_fix_operator_scope_or_absent_atoms():
    request = (
        "On the return segment only, depart no earlier than 09:16:00. "
        "On the outbound segment only, depart no later than 07:30:00."
    )
    atoms = tuple(
        Atom(kind="atom", op=op, scope=scope, unit="seconds", value=value)
        for op, scope, value in [
            ("depart_ge", "return", 3696),
            ("depart_ge", "outbound", 1234),
            ("arrive_by", "return", 90000),
        ]
    )
    expr = All(kind="all", children=atoms)
    changed, log = mechanism.normalize_time_values(request, expr)
    assert changed.children[0].value == 33360
    assert changed.children[1:] == expr.children[1:]  # no op reversal or invented-bound removal
    assert len(log) == 1 and expr.children[0].value == 3696  # no mutation
    ambiguous = "Depart no earlier than 09:00:00. Depart no earlier than 09:30:00."
    unchanged, log = mechanism.normalize_time_values(ambiguous, atoms[1])
    assert unchanged == atoms[1] and not log
    assert mechanism.time_mentions("Arrive by 25:01:02.")[0]["seconds"] == 90062
