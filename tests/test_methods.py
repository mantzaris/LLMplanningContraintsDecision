import json
from plancheck.budget import Journal
from plancheck.constraints import ADAPTER, response_json
from plancheck.methods import run_method
from plancheck.model import ModelCalls
from plancheck.prompts import judgment_prompt, translation_prompt
from test_logic import atom


def test_all_methods_and_controlled_replay(scenario, pool, tmp_path):
    omitted = ADAPTER.validate_json('{"kind":"all","children":[]}')
    correct = ADAPTER.validate_json(
        json.dumps(
            {
                "kind": "all",
                "children": [
                    atom("depart_ge", 150).model_dump(mode="json"),
                    atom("permit_modes", ["bus"], "mode").model_dump(mode="json"),
                ],
            }
        )
    )
    translations = [omitted, atom("depart_ge", 150), atom("permit_modes", ["bus"], "mode"), correct]
    outputs = {
        judgment_prompt(scenario, j): json.dumps(
            {
                "verdict": "satisfied" if j.journey_id == "d" else "violated",
                "spans": [],
                "reason": "injected diagnostic label",
            }
        )
        for j in pool
    }

    class Injected:
        metadata = {"identifier": "explicit-scripted-diagnostic"}

        def generate(self, prompt, seed, *args):
            if prompt == translation_prompt(scenario):
                raw = response_json(translations[seed - 104])
            elif prompt in outputs:
                raw = outputs[prompt]
            else:
                raw = response_json(correct)
            return {
                "text": raw,
                "input_tokens": len(prompt.split()),
                "output_tokens": len(raw.split()),
                "latency_seconds": 0.0,
            }

    config = {
        "candidate_count": 4,
        "method_call_limit": 7,
        "max_new_tokens": 768,
        "temperature": 0.7,
        "seed": 104,
        "solver_timeout_ms": 5000,
        "repair_limit": 1,
        "judgment_limit": 2,
    }
    backend = Injected()
    calls = ModelCalls(Journal(tmp_path / "calls.jsonl"), backend.metadata, backend)
    results = {m: run_method(m, scenario, pool, calls, config) for m in "ABCDE"}
    assert results["A"]["plan_id"] == "a"
    assert results["B"]["plan_id"] == "d"
    assert results["C"]["plan_id"] == "d"
    assert results["D"]["translations"] == results["E"]["translations"]
    assert results["D"]["candidates"] == results["E"]["candidates"] or [
        c["signature"] for c in results["D"]["candidates"]
    ] == [c["signature"] for c in results["E"]["candidates"]]
    replay = ModelCalls(Journal(tmp_path / "calls.jsonl"), backend.metadata)
    for method in "ABCDE":
        again = run_method(method, scenario, pool, replay, config)
        assert again["plan_id"] == results[method]["plan_id"]
        assert again["judgments"] == results[method]["judgments"]
    assert any(r["repairs"] for r in results.values())


def test_critique_can_damage_correct_output(scenario, pool, tmp_path):
    from plancheck.reference import evaluate

    correct = atom("depart_ge", 200)
    omitted = ADAPTER.validate_json('{"kind":"all","children":[]}')

    class Injected:
        metadata = {"identifier": "harmful-repair-injected"}

        def generate(self, prompt, *args):
            raw = response_json(correct if prompt == translation_prompt(scenario) else omitted)
            return {"text": raw, "input_tokens": 1, "output_tokens": 1, "latency_seconds": 0.0}

    b = Injected()
    calls = ModelCalls(Journal(tmp_path / "calls.jsonl"), b.metadata, b)
    config = {
        "candidate_count": 4,
        "method_call_limit": 7,
        "max_new_tokens": 768,
        "temperature": 0.7,
        "seed": 104,
        "solver_timeout_ms": 5000,
        "repair_limit": 1,
        "judgment_limit": 2,
    }
    output = run_method("B", scenario, pool, calls, config)
    reference = {"requirement": "earliest_departure", "target": 200, "direction": "outbound"}
    assert evaluate(reference, pool, output)["repair_damaged_correct_plan"]
