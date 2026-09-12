"""Prediction compiler. Finite-domain Z3 encoding of journey attributes."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable
import z3
from .constraints import All, Atom, Expression, Not
from .domain import Journey, objective


def scoped_rides(journey: Journey, scope: str):
    return [r for r in journey.rides if scope == "all" or r.scope == scope]


def atom_value(atom: Atom, journey: Journey) -> bool:
    rides = scoped_rides(journey, atom.scope)
    if not rides:
        return False
    value = atom.value
    if atom.op == "arrive_by":
        return rides[-1].arrival <= value
    if atom.op == "depart_ge":
        return rides[0].departure >= value
    if atom.op == "depart_le":
        return rides[0].departure <= value
    if atom.op == "max_transfers":
        return (
            sum(sum(r.scope == scope for r in rides) - 1 for scope in {r.scope for r in rides})
            <= value
        )
    if atom.op == "permit_modes":
        return all(r.mode in value for r in rides)
    if atom.op == "exclude_modes":
        return all(r.mode not in value for r in rides)
    if atom.op == "visits":
        stops = []
        for ride in rides:
            for call in ride.calls:
                if not stops or stops[-1] != call.stop_id:
                    stops.append(call.stop_id)
        cursor = 0
        for stop in value:
            try:
                cursor = stops.index(stop, cursor) + 1
            except ValueError:
                return False
        return True
    raise ValueError(atom.op)


def predicate(expr: Expression, journey: Journey) -> bool:
    if isinstance(expr, Atom):
        return atom_value(expr, journey)
    if isinstance(expr, All):
        return all(predicate(child, journey) for child in expr.children)
    if isinstance(expr, Not):
        return not predicate(expr.child, journey)
    raise TypeError(type(expr))


def compile_z3(expr: Expression, index: z3.ArithRef, pool: list[Journey]) -> z3.BoolRef:
    if isinstance(expr, All):
        return z3.And([compile_z3(c, index, pool) for c in expr.children])
    if isinstance(expr, Not):
        return z3.Not(compile_z3(expr.child, index, pool))
    return z3.Or([index == i for i, j in enumerate(pool) if atom_value(expr, j)])


@dataclass(frozen=True)
class PlanResult:
    status: str
    plan_id: str | None
    solver_seconds: float
    reason: str | None = None


def solve(
    expr: Expression, pool: list[Journey], timeout_ms: int = 5000, check: Callable | None = None
) -> PlanResult:
    start = perf_counter()
    if timeout_ms <= 0:
        return PlanResult("timeout", None, 0.0, "deadline exhausted before solve")
    ordered = sorted(pool, key=objective)
    solver = z3.Solver()
    solver.set(timeout=timeout_ms)
    index = z3.Int("journey_index")
    solver.add(index >= 0, index < len(ordered), compile_z3(expr, index, ordered))

    def query():
        remaining = timeout_ms - int((perf_counter() - start) * 1000)
        if remaining <= 0:
            return z3.unknown
        solver.set(timeout=remaining)
        return check(solver) if check else solver.check()

    status = query()
    if status == z3.unsat:
        return PlanResult("infeasible_in_pool", None, perf_counter() - start)
    if status != z3.sat:
        return PlanResult("timeout", None, perf_counter() - start, solver.reason_unknown())
    low, high = 0, len(ordered) - 1
    while low < high:
        middle = (low + high) // 2
        solver.push()
        solver.add(index <= middle)
        status = query()
        solver.pop()
        if status == z3.unknown:
            return PlanResult(
                "timeout", None, perf_counter() - start, "unknown during optimum search"
            )
        if status == z3.sat:
            high = middle
        else:
            low = middle + 1
    return PlanResult("satisfiable", ordered[low].journey_id, perf_counter() - start)
