"""Small JSON constraint AST. No executable text is accepted."""

from __future__ import annotations

import json
from typing import Annotated, Literal, Union
from pydantic import Field, TypeAdapter, ValidationError
from .domain import Mode, PublicScenario, StrictModel
from .util import canonical


class Span(StrictModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class Atom(StrictModel):
    kind: Literal["atom"]
    op: Literal[
        "arrive_by",
        "depart_ge",
        "depart_le",
        "max_transfers",
        "permit_modes",
        "exclude_modes",
        "visits",
    ]
    scope: str
    value: int | tuple[Mode, ...] | tuple[str, ...]
    unit: Literal["seconds", "count", "mode", "stop_id"]
    source: Span | None = None


class All(StrictModel):
    kind: Literal["all"]
    children: tuple["Expression", ...]
    source: Span | None = None


class Not(StrictModel):
    kind: Literal["not"]
    child: "Expression"
    source: Span | None = None


Expression = Annotated[Union[Atom, All, Not], Field(discriminator="kind")]
All.model_rebuild()
Not.model_rebuild()
ADAPTER = TypeAdapter(Expression)


class Interpretation(StrictModel):
    status: Literal["ok", "unsupported"]
    formula: Expression | None
    unsupported: tuple[str, ...] = ()


class InterpretationError(ValueError):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


def nodes(expr: Expression):
    yield expr
    if isinstance(expr, All):
        for child in expr.children:
            yield from nodes(child)
    elif isinstance(expr, Not):
        yield from nodes(expr.child)


def parse_interpretation(raw: str, scenario: PublicScenario) -> Expression:
    try:
        result = Interpretation.model_validate_json(raw)
    except (ValidationError, ValueError) as error:
        raise InterpretationError("malformed", str(error)) from error
    if result.status == "unsupported":
        raise InterpretationError("unsupported", "; ".join(result.unsupported))
    if result.formula is None or result.unsupported:
        raise InterpretationError("malformed", "ok requires a formula and no unsupported items")
    for node in nodes(result.formula):
        if node.source and not (node.source.start < node.source.end <= len(scenario.request)):
            raise InterpretationError("malformed", "invalid source span offsets")
        if not isinstance(node, Atom):
            continue
        if node.scope not in {"all", *(s.scope for s in scenario.segments)}:
            raise InterpretationError("entity_resolution_failure", f"unknown scope {node.scope}")
        expected = (
            "seconds"
            if node.op in {"arrive_by", "depart_ge", "depart_le"}
            else "count"
            if node.op == "max_transfers"
            else "stop_id"
            if node.op == "visits"
            else "mode"
        )
        if node.unit != expected:
            raise InterpretationError("malformed", "incorrect units")
        if expected in {"seconds", "count"}:
            if type(node.value) is not int or node.value < 0:
                raise InterpretationError("malformed", "expected nonnegative integer")
        elif not isinstance(node.value, tuple) or not node.value:
            raise InterpretationError("malformed", "expected nonempty entity list")
        elif expected == "stop_id" and any(v not in scenario.stops for v in node.value):
            raise InterpretationError("entity_resolution_failure", "unknown stop_id")
        elif expected == "mode" and any(
            v not in {"bus", "tram", "rail", "subway", "ferry", "cable", "gondola", "funicular"}
            for v in node.value
        ):
            raise InterpretationError("entity_resolution_failure", "unknown mode")
    return result.formula


def syntax_key(expr: Expression) -> str:
    """Ignore traceability pointers; conjunction order is immaterial."""

    def clean(node):
        item = node.model_dump(mode="json", exclude={"source"})
        if isinstance(node, All):
            item["children"] = sorted((clean(c) for c in node.children), key=canonical)
        if isinstance(node, Not):
            item["child"] = clean(node.child)
        return item

    return canonical(clean(expr))


def response_json(expr: Expression) -> str:
    return json.dumps({"status": "ok", "formula": expr.model_dump(mode="json"), "unsupported": []})
