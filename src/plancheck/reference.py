"""Independent offline checker, never imported by inference modules.

Consumes separately authored reference rule dictionaries, not the prediction AST.
Uses its own traversal, transfer arithmetic, and subsequence algorithm.
"""

from __future__ import annotations
from typing import Any
from .domain import Journey


def check_reference(rule: dict[str, Any], journey: Journey) -> bool:
    if "and" in rule:
        return all(check_reference(part, journey) for part in rule["and"])
    if "negate" in rule:
        return not check_reference(rule["negate"], journey)
    direction = rule["direction"]
    selected = tuple(leg for leg in journey.rides if direction == "all" or leg.scope == direction)
    if len(selected) == 0:
        return False
    requirement = rule["requirement"]
    target = rule["target"]
    if requirement == "latest_arrival":
        return selected[-1].calls[-1].arrival_s <= target
    if requirement == "earliest_departure":
        return target <= selected[0].calls[0].departure_s
    if requirement == "latest_departure":
        return selected[0].calls[0].departure_s <= target
    if requirement == "transfer_limit":
        previous = None
        transfers = 0
        for leg in selected:
            if previous == leg.scope:
                transfers += 1
            previous = leg.scope
        return transfers <= target
    if requirement == "allowed_modes":
        return set(leg.mode for leg in selected).issubset(set(target))
    if requirement == "forbidden_modes":
        return not set(leg.mode for leg in selected).intersection(target)
    if requirement == "ordered_calls":
        wanted = iter(target)
        next_stop = next(wanted, None)
        last_stop = None
        for leg in selected:
            for call in leg.calls:
                if call.stop_id != last_stop and call.stop_id == next_stop:
                    next_stop = next(wanted, None)
                last_stop = call.stop_id
        return next_stop is None
    raise ValueError(f"Unsupported reference rule: {requirement}")


def evaluate(reference: dict, pool: list[Journey], output: dict) -> dict:
    feasible_ids = {j.journey_id for j in pool if check_reference(reference, j)}
    plan_id = output.get("plan_id")
    initial_id = output.get("initial_plan_id")
    returned = plan_id is not None
    correct = returned and plan_id in feasible_ids
    initial_correct = initial_id is not None and initial_id in feasible_ids
    infeasible_claim = output.get("status") == "infeasible_in_pool"
    return {
        "reference_feasible_count": len(feasible_ids),
        "complete_satisfaction": correct,
        "invalid_plan_returned": returned and not correct,
        "false_infeasibility": infeasible_claim and bool(feasible_ids),
        "correct_infeasibility": infeasible_claim and not feasible_ids,
        "unresolved": output.get("semantic_status") != "resolved_by_model",
        "plan_coverage": returned,
        "initial_plan_correct": initial_correct,
        "repair_damaged_correct_plan": bool(output.get("repairs"))
        and initial_correct
        and not correct,
    }
