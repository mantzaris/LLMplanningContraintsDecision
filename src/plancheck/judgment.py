"""Structured judgments and explicit contradiction tracking."""

from __future__ import annotations
from typing import Literal
from .constraints import Span
from .domain import StrictModel


class Judgment(StrictModel):
    verdict: Literal["satisfied", "violated", "uncertain"]
    spans: tuple[Span, ...]
    reason: str


def parse_judgment(raw: str, request: str) -> Judgment:
    judgment = Judgment.model_validate_json(raw)
    if any(not (s.start < s.end <= len(request)) for s in judgment.spans):
        raise ValueError("Judgment source span outside request")
    return judgment


def labels_from_judgments(judgments: list[dict]) -> tuple[dict[str, bool], list[str]]:
    labels = {}
    contradictions = []
    for item in judgments:
        verdict = item["judgment"]["verdict"]
        if verdict == "uncertain":
            continue
        key = item["journey_id"]
        value = verdict == "satisfied"
        if key in labels and labels[key] != value:
            contradictions.append(key)
        labels[key] = value
    return labels, sorted(set(contradictions))
