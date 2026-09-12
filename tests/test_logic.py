import json
from itertools import product
import pytest
import z3
from plancheck.compiler import predicate, compile_z3, solve
from plancheck.constraints import ADAPTER, InterpretationError, parse_interpretation
from plancheck.domain import Journey
from plancheck.reference import check_reference
from conftest import ride


def atom(op, value, unit="seconds", scope="outbound"):
    return ADAPTER.validate_json(
        json.dumps({"kind": "atom", "op": op, "scope": scope, "value": value, "unit": unit})
    )


def test_exhaustive_symbolic_and_independent_reference(pool):
    mapping = {
        "arrive_by": "latest_arrival",
        "depart_ge": "earliest_departure",
        "depart_le": "latest_departure",
        "max_transfers": "transfer_limit",
        "permit_modes": "allowed_modes",
        "exclude_modes": "forbidden_modes",
        "visits": "ordered_calls",
    }
    atoms = [
        (op, v, "seconds")
        for op, v in product(
            ("arrive_by", "depart_ge", "depart_le"), (99, 100, 149, 150, 199, 200, 201, 250, 300)
        )
    ]
    atoms += [("max_transfers", n, "count") for n in (0, 1, 2)]
    atoms += [
        (op, modes, "mode")
        for op, modes in product(
            ("permit_modes", "exclude_modes"), (["bus"], ["tram"], ["bus", "tram"])
        )
    ]
    atoms += [
        ("visits", stops, "stop_id")
        for stops in (["A", "C"], ["A", "B", "C"], ["C", "A"], ["B", "B"])
    ]
    for op, value, unit in atoms:
        expr = atom(op, value, unit)
        ref = {"requirement": mapping[op], "target": value, "direction": "outbound"}
        for negated in (False, True):
            expression = (
                ADAPTER.validate_json(
                    json.dumps({"kind": "not", "child": expr.model_dump(mode="json")})
                )
                if negated
                else expr
            )
            reference = {"negate": ref} if negated else ref
            for index, journey in enumerate(pool):
                expected = check_reference(reference, journey)
                assert predicate(expression, journey) == expected
                selected = z3.Int("selected")
                solver = z3.Solver()
                solver.add(selected == index, compile_z3(expression, selected, pool) != expected)
                assert solver.check() == z3.unsat


def test_omission_negation_and_scope(pool):
    correct = atom("depart_ge", 150)
    omitted = ADAPTER.validate_json('{"kind":"all","children":[]}')
    incorrect_negation = ADAPTER.validate_json(
        json.dumps({"kind": "not", "child": correct.model_dump(mode="json")})
    )
    assert solve(correct, pool).plan_id == "c"
    assert solve(omitted, pool).plan_id == "a"
    assert solve(incorrect_negation, pool).plan_id == "a"
    roundtrip = Journey(
        journey_id="rt",
        rides=(ride("out", "A", "C", 100, 200), ride("back", "C", "A", 300, 400, "tram", "return")),
    )
    assert predicate(atom("exclude_modes", ["tram"], "mode", "outbound"), roundtrip)
    assert not predicate(atom("exclude_modes", ["tram"], "mode", "return"), roundtrip)
    assert predicate(atom("max_transfers", 0, "count", "all"), roundtrip)
    assert check_reference(
        {"requirement": "transfer_limit", "target": 0, "direction": "all"}, roundtrip
    )


def test_outcomes(pool):
    assert solve(atom("arrive_by", 199), pool).status == "infeasible_in_pool"
    assert solve(atom("arrive_by", 200), pool).plan_id == "a"
    assert solve(atom("arrive_by", 200), pool, timeout_ms=0).status == "timeout"
    assert solve(atom("arrive_by", 200), pool, check=lambda _: z3.unknown).status == "timeout"
    assert solve(atom("arrive_by", 200), []).status == "infeasible_in_pool"


@pytest.mark.parametrize(
    "raw,status",
    [
        ("print(1)", "malformed"),
        ('{"status":"unsupported","formula":null,"unsupported":["capacity"]}', "unsupported"),
        (
            '{"status":"ok","formula":{"kind":"atom","op":"visits","scope":"outbound","value":["unknown"],"unit":"stop_id"}}',
            "entity_resolution_failure",
        ),
        (
            '{"status":"ok","formula":{"kind":"atom","op":"arrive_by","scope":"return","value":200,"unit":"seconds"}}',
            "entity_resolution_failure",
        ),
        (
            '{"status":"ok","formula":{"kind":"atom","op":"arrive_by","scope":"outbound","value":200,"unit":"count"}}',
            "malformed",
        ),
    ],
)
def test_structured_errors(scenario, raw, status):
    with pytest.raises(InterpretationError) as error:
        parse_interpretation(raw, scenario)
    assert error.value.status == status


def test_conjunction(pool):
    expr = ADAPTER.validate_json(
        json.dumps(
            {
                "kind": "all",
                "children": [
                    atom("depart_ge", 150).model_dump(mode="json"),
                    atom("exclude_modes", ["tram"], "mode").model_dump(mode="json"),
                ],
            }
        )
    )
    assert solve(expr, pool).plan_id == "d"
