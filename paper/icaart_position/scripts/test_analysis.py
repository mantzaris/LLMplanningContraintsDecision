"""Focused checks for manuscript-only analysis risks; no experiment regeneration."""

import importlib.util
import json
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "paper_analysis", Path(__file__).with_name("analyze.py")
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
DATA = Path(__file__).resolve().parents[1] / "analysis"


def test_equal_marginals_do_not_determine_joint_cells():
    diagonal = [{"G": True, "S": True}, {"G": False, "S": False}]
    off_diagonal = [{"G": True, "S": False}, {"G": False, "S": True}]
    assert MODULE.joint_counts(diagonal) != MODULE.joint_counts(off_diagonal)
    assert MODULE.joint_counts(off_diagonal)["G0S1"] == 1


def test_saved_joint_counts_and_direct_baseline_pairing():
    data = json.loads((DATA / "stage3-summary.json").read_text())
    finals = {r["arm"]: r for r in data["checkpoints"] if r["checkpoint"] == 8}
    for arm, values in {"A": (27, 0, 1, 4), "B": (28, 3, 0, 1), "C": (25, 0, 0, 7)}.items():
        assert tuple(finals[arm][k] for k in ["G1S1", "G1S0", "G0S1", "G0S0"]) == values
        assert sum(values) == 32
    pair = next(
        r
        for r in data["paired"]
        if r["left"] == "A" and r["right"] == "B" and r["checkpoint"] == 8 and r["metric"] == "S"
    )
    assert (pair["wins"], pair["ties"], pair["losses"]) == (1, 30, 1)


def test_truthful_witness_replay_is_not_best_output_oracle():
    case = json.loads((DATA / "worked-examples.json").read_text())["sampling-20"]
    row = case["row"]
    assert not row["G"] and row["S"] and not row["oracle_witness_correct"]
    assert row["any_candidate_selected_plan_correct"]
    updates = case["ordinary"]["updates"]
    assert [u["reference_accepts"] for u in updates] == [False, True]
    assert [u["judgment"]["verdict"] for u in updates] == ["satisfied", "satisfied"]


def test_matching_candidate_loss_is_traced_not_assumed():
    cases = json.loads((DATA / "selection-failures.json").read_text())
    final = [c for c in cases if c["checkpoint"] == 8]
    assert {c["scenario_id"] for c in final} == {"sampling-12", "sampling-25", "sampling-28"}
    for c in cases:
        assert c["cause"] == "incorrect_judgment_eliminated_matching_candidate"
        assert c["destructive_updates"]
        for update in c["destructive_updates"]:
            assert (update["judgment"]["verdict"] == "satisfied") != update["reference_accepts"]
            assert not set(c["matching_candidate_ids"]).intersection(update["after"])
    assert sum(not c["destructive_updates"][0]["reference_accepts"] for c in final) == 2
