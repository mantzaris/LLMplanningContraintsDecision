"""Bounded mechanism checks; synthetic fixtures are not research observations."""

import ast
from pathlib import Path
import pytest
from plancheck.budget import BudgetExceeded, Journal
from plancheck.constraints import ADAPTER
from plancheck.model import ModelCalls
from plancheck.semantic_sampling import behavior, feedback, parse_sample, prefix_bundle, TokenCalls
from plancheck.source_normalization import normalize_time_values
from plancheck.util import canonical


def expr(value):
    return ADAPTER.validate_json(canonical(value))


def atom(op, value):
    return {"kind": "atom", "op": op, "scope": "outbound", "value": value, "unit": "seconds"}


def test_full_equivalence_and_masking(pool, scenario):
    a = expr(atom("depart_ge", 120))
    b = expr(atom("depart_ge", 110))
    assert (
        behavior(a, pool, scenario.request)["signature"]
        == behavior(b, pool, scenario.request)["signature"]
    )
    left = expr({"kind": "all", "children": [atom("arrive_by", 0), atom("depart_ge", 120)]})
    right = expr({"kind": "all", "children": [atom("arrive_by", 0), atom("depart_ge", 200)]})
    x, y = [behavior(e, pool, scenario.request) for e in (left, right)]
    assert x["signature"] == y["signature"] == [False] * 4
    assert x["clauses"][1]["signature"] != y["clauses"][1]["signature"]


def test_prefix_and_feedback_isolation(pool, scenario):
    samples = [
        {
            **parse_sample(
                canonical({"status": "ok", "formula": atom("depart_ge", v), "unsupported": []}),
                scenario,
                pool,
            ),
            "call": {"charged_tokens": 20},
        }
        for v in (100, 100, 200)
    ]
    before = prefix_bundle(samples, 2, pool, 5000)
    assert len(before["candidates"]) == 1
    assert before["attempts"] == 2 and before["generation_tokens"] == 40
    assert len(prefix_bundle(samples, 3, pool, 5000)["candidates"]) == 2
    first = feedback(scenario, pool, samples)
    for s in samples:
        s.update(
            reference="PRIVATE_SENTINEL", oracle="PRIVATE_SENTINEL", winning_arm="PRIVATE_SENTINEL"
        )
    assert feedback(scenario, pool, samples) == first
    assert "PRIVATE_SENTINEL" not in first
    assert "Repeating any interpretation is permitted" in first
    for filename in ("semantic_sampling.py", "sampling_run.py", "source_normalization.py"):
        tree = ast.parse((Path("src/plancheck") / filename).read_text())
        imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any("reference" in m or "analysis" in m or "sampling_data" in m for m in imports)


@pytest.mark.parametrize("fails", [False, True])
def test_token_admission_failure_duplicate_and_resume(tmp_path, fails):
    class Backend:
        def __init__(self):
            self.n = 0

        def generate(self, *args):
            self.n += 1
            if fails:
                raise RuntimeError("deliberate diagnostic failure")
            return {
                "text": "malformed but charged",
                "input_tokens": 10,
                "output_tokens": 4,
                "latency_seconds": 1.0,
            }

    backend = Backend()
    path = tmp_path / "calls.jsonl"
    t = TokenCalls(ModelCalls(Journal(path), {}, backend), lambda _: 10)
    with pytest.raises(BudgetExceeded):
        t.invoke("x", 1, 8, 0.7, "translation", "A", 17)
    assert backend.n == 0
    a = t.invoke("x", 1, 8, 0.7, "translation", "A", 18)
    b = t.invoke("x", 1, 8, 0.7, "translation", "B", 18)
    replay = TokenCalls(ModelCalls(Journal(path), {}))
    c = replay.invoke("x", 1, 8, 0.7, "translation", "C", 18)
    assert backend.n == 1
    assert (
        a["charged_tokens"] == b["charged_tokens"] == c["charged_tokens"] == (18 if fails else 14)
    )
    assert b["cached"] and c["cached"]
    assert len([e for e in Journal(path).read() if e["event"] == "generation_start"]) == 1


def test_source_only_normalization():
    formula = expr(atom("depart_ge", 1000))
    fixed, changes = normalize_time_values(
        "On the outbound segment only, depart no earlier than 10:30:00.", formula
    )
    assert fixed.value == 37800 and changes
    unchanged, changes = normalize_time_values(
        "On the return segment only, depart no earlier than 10:30:00.", formula
    )
    assert unchanged == formula and not changes


def test_prefix_validation_uses_only_current_bundle_and_charges_judge(pool, scenario):
    from plancheck.semantic_sampling import validate_prefix

    samples = [
        {
            **parse_sample(
                canonical({"status": "ok", "formula": atom("depart_ge", v), "unsupported": []}),
                scenario,
                pool,
            ),
            "call": {"charged_tokens": 20},
        }
        for v in (100, 200)
    ]
    bundle = prefix_bundle(samples, 2, pool, 5000)

    class Judge:
        def __init__(self):
            self.prompts = []

        def invoke(self, prompt, *args):
            self.prompts.append(prompt)
            assert "Represented full behaviors" not in prompt
            assert "signature_hash" not in prompt
            return {
                "raw": canonical(
                    {"verdict": "violated", "spans": [], "reason": "diagnostic fixed judgment"}
                ),
                "failed": False,
                "charged_tokens": 123,
            }

    judge = Judge()
    cfg = {"seed": 31000, "max_new_tokens": 768, "validation_tokens_per_prefix": 4000}
    result = validate_prefix(bundle, scenario, pool, judge, cfg, "unit")
    assert len(judge.prompts) == 1
    assert result["validation_tokens"] == 123
    assert result["plan_id"] == "d"
    assert result["repairs"] == []
    assert "no_distinguishing_witness_in_completed_pool" in result["events"]
