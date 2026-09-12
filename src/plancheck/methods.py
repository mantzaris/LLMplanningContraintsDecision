"""Functional A–E methods. No imports or parameters expose hidden annotations."""

from __future__ import annotations
from dataclasses import asdict
from .budget import BudgetExceeded
from .compiler import predicate
from .constraints import InterpretationError, parse_interpretation, response_json
from .domain import Journey, PublicScenario, objective
from .judgment import labels_from_judgments, parse_judgment
from .model import ModelCalls
from .prompts import critique_prompt, judgment_prompt, repair_prompt, translation_prompt
from .render import render_journey
from .selection import candidates, select_witness
from .util import digest


def run_method(
    method: str, scenario: PublicScenario, pool: list[Journey], calls: ModelCalls, config: dict
) -> dict:
    if method not in "ABCDE" or len(method) != 1:
        raise ValueError(method)
    owner = f"{scenario.scenario_id}/{method}"
    logical_start = len(calls.logical)
    output = {
        "method": method,
        "scenario_id": scenario.scenario_id,
        "base_id": scenario.base_id,
        "status": "unresolved",
        "semantic_status": "unverified",
        "plan_id": None,
        "initial_plan_id": None,
        "translations": [],
        "candidates": [],
        "witnesses": [],
        "judgments": [],
        "repairs": [],
        "errors": [],
        "events": [],
    }
    allowance = config["method_call_limit"]
    used_calls = 0

    def invoke(prompt, purpose, seed):
        nonlocal used_calls
        if used_calls >= allowance:
            raise BudgetExceeded("per-method logical call allowance exhausted")
        used_calls += 1
        return calls.call(
            prompt,
            seed,
            config["max_new_tokens"],
            config["temperature"] if purpose == "translation" else 0.0,
            purpose,
            owner,
        )

    expressions = []
    initial = None
    active = []
    try:
        count = config["candidate_count"] if method in "DE" else 1
        for index in range(count):
            raw = invoke(translation_prompt(scenario), "translation", config["seed"] + index)
            output["translations"].append(raw)
            try:
                expr = parse_interpretation(raw, scenario)
                expressions.append(expr)
            except InterpretationError as error:
                output["errors"].append(
                    {
                        "phase": "translation",
                        "index": index,
                        "status": error.status,
                        "detail": str(error),
                    }
                )
        active = candidates(expressions, pool, config["solver_timeout_ms"])
        output["candidates"] = [c.record() for c in active]
        if active:
            initial = active[0]
            output["initial_plan_id"] = initial.plan.plan_id
        if method == "B":
            draft = output["translations"][0]
            for _ in range(config["repair_limit"]):
                raw = invoke(critique_prompt(scenario, draft), "critique", config["seed"])
                output["repairs"].append(
                    {"kind": "ordinary_critique", "draft": draft, "response": raw}
                )
                expr = parse_interpretation(raw, scenario)
                active = candidates([expr], pool, config["solver_timeout_ms"])
                draft = raw
        elif method in "CDE" and active:
            used = set()
            for query_index in range(config["judgment_limit"]):
                if method in "DE":
                    witness = select_witness(
                        active, pool, used, "balanced" if method == "D" else "consequence"
                    )
                    if witness is None:
                        output["events"].append("no_distinguishing_witness_in_completed_pool")
                        break
                else:
                    # SSV adaptation: alternate concrete satisfying and violating
                    # instances of the initial formula, independently judged against NL.
                    desired = query_index % 2 == 0
                    options = [
                        j
                        for j in sorted(pool, key=objective)
                        if j.journey_id not in used and predicate(initial.expression, j) == desired
                    ]
                    if not options:
                        output["events"].append(
                            f"no_{'positive' if desired else 'negative'}_example"
                        )
                        continue
                    witness = {
                        "journey_id": options[0].journey_id,
                        "policy": "positive_negative_adaptation",
                        "predicted_label": desired,
                    }
                journey = next(j for j in pool if j.journey_id == witness["journey_id"])
                used.add(journey.journey_id)
                output["witnesses"].append(witness)
                # Seed depends on public example, never selector identity or vote.
                seed = config["seed"] + int(digest(journey.journey_id)[:6], 16)
                raw = invoke(judgment_prompt(scenario, journey), "judgment", seed)
                try:
                    judgment = parse_judgment(raw, scenario.request).model_dump(mode="json")
                except ValueError as error:
                    judgment = {"verdict": "uncertain", "spans": [], "reason": "malformed judgment"}
                    output["errors"].append(
                        {"phase": "judgment", "status": "malformed", "detail": str(error)}
                    )
                output["judgments"].append(
                    {"journey_id": journey.journey_id, "judgment": judgment, "raw": raw}
                )
                labels, contradictions = labels_from_judgments(output["judgments"])
                if contradictions:
                    output["events"].append("contradictory_judgments")
                    active = []
                    break
                active = [
                    c
                    for c in active
                    if all(
                        predicate(c.expression, j) == labels[j.journey_id]
                        for j in pool
                        if j.journey_id in labels
                    )
                ]
                if not active:
                    output["events"].append("all_candidates_eliminated")
                    break
            # Same bounded repair allowance and trigger for D/E. Retain initial for
            # diagnostics, but accept repair only if it agrees with every definite label.
            if not active:
                labels, contradictions = labels_from_judgments(output["judgments"])
                for _ in range(0 if contradictions else config["repair_limit"]):
                    feedback = [
                        {
                            "journey": render_journey(
                                next(j for j in pool if j.journey_id == item["journey_id"]),
                                scenario,
                            ),
                            "judgment": item["judgment"],
                        }
                        for item in output["judgments"]
                    ]
                    raw = invoke(
                        repair_prompt(scenario, response_json(initial.expression), feedback),
                        "repair",
                        config["seed"],
                    )
                    output["repairs"].append({"kind": "example_feedback", "response": raw})
                    expr = parse_interpretation(raw, scenario)
                    if all(
                        predicate(expr, j) == labels[j.journey_id]
                        for j in pool
                        if j.journey_id in labels
                    ):
                        active = candidates([expr], pool, config["solver_timeout_ms"])
                        break
                    output["events"].append("repair_contradicts_judgments")
        if active:
            chosen = active[0]  # Stable generation order, not hidden-label best-of-k.
            output.update(
                status=chosen.plan.status,
                plan_id=chosen.plan.plan_id,
                final_formula=chosen.expression.model_dump(mode="json"),
                final_solver=asdict(chosen.plan),
                remaining_candidates=len(active),
            )
            definite = any(j["judgment"]["verdict"] != "uncertain" for j in output["judgments"])
            if len(active) == 1 and definite:
                output["semantic_status"] = "resolved_by_model"
            elif len(active) > 1:
                output["semantic_status"] = "unresolved_multiple_candidates"
            else:
                output["semantic_status"] = "unverified_no_semantic_evidence"
        elif initial:
            output["diagnostic_fallback_plan_id"] = initial.plan.plan_id
            output["semantic_status"] = "unresolved_candidate_exhaustion"
        elif output["errors"]:
            output["status"] = output["errors"][0]["status"]
    except (
        BudgetExceeded,
        TimeoutError,
        InterpretationError,
        ValueError,
        KeyError,
        RuntimeError,
    ) as error:
        output["errors"].append(
            {
                "phase": "method",
                "status": getattr(error, "status", type(error).__name__),
                "detail": str(error),
            }
        )
        output["semantic_status"] = "unresolved_error"
        if initial:
            output["diagnostic_fallback_plan_id"] = initial.plan.plan_id
    output["logical_calls"] = calls.logical[logical_start:]
    return output
