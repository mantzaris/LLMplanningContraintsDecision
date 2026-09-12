from pathlib import Path
import pytest
from plancheck.budget import GPUBudget, BudgetExceeded, Journal
from plancheck.judgment import labels_from_judgments, parse_judgment
from plancheck.model import ModelCalls
from plancheck.prompts import judgment_prompt
from plancheck.runner import run


def test_request_guard_and_resume(tmp_path):
    path = tmp_path / "budget.jsonl"
    first = GPUBudget(path, request_limit=2)
    first.start()
    first.request()
    first.close()
    second = GPUBudget(path, request_limit=2)
    second.start()
    second.request()
    with pytest.raises(BudgetExceeded):
        second.request()
    second.close()
    assert sum(e["event"] == "request_start" for e in Journal(path).read()) == 2


def test_crash_reservation_and_elapsed_guard(tmp_path):
    path = tmp_path / "budget.jsonl"
    Journal(path).append({"event": "session_start", "session": "crashed", "reserved_seconds": 3600})
    budget = GPUBudget(path)
    with pytest.raises(BudgetExceeded):
        budget.start()
    budget.close()
    with pytest.raises(ValueError):
        GPUBudget(tmp_path / "bad", request_limit=101)
    short = GPUBudget(tmp_path / "short", seconds_limit=1)
    short.start()
    short.started -= 2
    with pytest.raises(BudgetExceeded):
        short.request()
    short.close()


def test_contradictory_and_uncertain_judgments():
    rows = [
        {"journey_id": "a", "judgment": {"verdict": v}}
        for v in ("satisfied", "uncertain", "violated")
    ]
    assert labels_from_judgments(rows)[1] == ["a"]
    assert labels_from_judgments(rows[:2]) == ({"a": True}, [])
    with pytest.raises(ValueError):
        parse_judgment(
            '{"verdict":"satisfied","spans":[{"start":0,"end":900}],"reason":"x"}', "short"
        )


def test_judge_boundary_and_gold_rejection(scenario, pool, tmp_path):
    prompt = judgment_prompt(scenario, pool[0])
    assert scenario.request in prompt and "trip t1" in prompt
    for forbidden in ("final_formula", "reference", "candidate", "vote", "preferred"):
        assert forbidden not in prompt
    with pytest.raises(ValueError, match="model judgments only"):
        run({"judge_mode": "gold"}, tmp_path, tmp_path / "run")
    # Static import boundary plus runtime public-only API: inference cannot import labels.
    package = Path(__file__).parents[1] / "src/plancheck"
    for name in ("methods", "model", "selection", "prompts", "runner"):
        import ast

        tree = ast.parse((package / f"{name}.py").read_text())
        assert not any(
            isinstance(n, ast.ImportFrom) and n.module in ("reference", "evaluation", "diagnostic")
            for n in ast.walk(tree)
        )


def test_cached_cost_and_failed_attempt_retention(tmp_path):
    class Stub:
        metadata = {"identifier": "explicit injected test"}
        n = 0

        def generate(self, *args):
            self.n += 1
            if self.n == 1:
                raise RuntimeError("injected failure")
            return {"text": "{}", "input_tokens": 10, "output_tokens": 2, "latency_seconds": 0.1}

    stub = Stub()
    journal = Journal(tmp_path / "calls.jsonl")
    calls = ModelCalls(journal, stub.metadata, stub)
    with pytest.raises(RuntimeError):
        calls.call("p", 1, 2, 0, "test", "A")
    assert calls.call("p", 1, 2, 0, "test", "A") == "{}"
    assert calls.call("p", 1, 2, 0, "test", "B") == "{}"
    assert stub.n == 2 and len(calls.logical) == 3
    replay = ModelCalls(journal, stub.metadata)
    assert replay.call("p", 1, 2, 0, "test", "D") == "{}"
    assert any(e["event"] == "generation_error" for e in journal.read())
    assert replay.logical[0]["input_tokens"] == 10
