"""Separate deterministic wording review; does not import the scenario constructor.

This narrow template grammar checks all requirement clauses, units and direction
against annotation dictionaries. It is an automated consistency check, not human review.
"""

from __future__ import annotations
import re
from pathlib import Path
from .reference import check_reference
from .runner import load_public
from .util import digest, immutable_json, read_json


def review_wording(request: str) -> dict:
    # Transport endpoints and the publicly declared 09–10 return window precede requirements.
    text = (
        request.split("outside these journeys. ")[-1]
        if "outside these journeys. " in request
        else request.split("]. ", 1)[1]
    )
    rules = []

    def add(name, target, direction="outbound"):
        rules.append({"requirement": name, "target": target, "direction": direction})

    for sentence in re.split(r"\.\s*", text.strip().rstrip(".")):
        direction = "outbound"
        scope = re.match(r"On the (outbound|return) segment only, (.*)", sentence)
        if scope:
            direction, sentence = scope.groups()
        sentence = sentence[0].upper() + sentence[1:]
        for clause in re.split(r" and (?=arrive)", sentence):
            clause = clause.strip().rstrip(",")
            clause = clause[0].upper() + clause[1:]
            clause = re.sub(r", (?:both )?inclusive$", "", clause)
            timing = re.fullmatch(
                r"(Depart no earlier than|Do not depart before|Depart no later than|Arrive by) (\d{2}):(\d{2}):(\d{2})",
                clause,
            )
            if timing:
                phrase, h, m, s = timing.groups()
                name = {
                    "Depart no earlier than": "earliest_departure",
                    "Do not depart before": "earliest_departure",
                    "Depart no later than": "latest_departure",
                    "Arrive by": "latest_arrival",
                }[phrase]
                add(name, int(h) * 3600 + int(m) * 60 + int(s), direction)
            elif match := re.fullmatch(r"Make at most (\d+) transfers", clause):
                add("transfer_limit", int(match[1]), direction)
            elif clause == "Make no transfers":
                add("transfer_limit", 0, direction)
            elif clause == "Do not use rail or tram":
                add("forbidden_modes", ["rail", "tram"], direction)
            elif clause == "Do not use buses":
                add("forbidden_modes", ["bus"], direction)
            elif clause == "Use only buses":
                add("allowed_modes", ["bus"], direction)
            elif match := re.fullmatch(
                r"Call at stop (\S+) and then stop (\S+), in that order; remaining aboard counts",
                clause,
            ):
                add("ordered_calls", [match[1], match[2]], direction)
            else:
                raise ValueError(f"Unreviewed wording: {clause}")
    return {"and": rules}


def review_collection(public: Path, references: Path, output: Path) -> dict:
    scenarios, pools = load_public(public)
    refs = {r["scenario_id"]: r for r in read_json(references)}
    rows = []
    for scenario in scenarios:
        reference = refs[scenario.scenario_id]["reference"]
        reviewed = review_wording(scenario.request)
        feasible = sum(check_reference(reference, j) for j in pools[scenario.pool_hash])
        rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "wording_matches": reviewed == reference,
                "reference_hash": digest(reference),
                "reference_feasible_count": feasible,
                "uncertain": reviewed != reference,
                "human_audited": False,
            }
        )
    result = {
        "review": "independent narrow grammar plus independent reference evaluation",
        "human_audited": False,
        "rows": rows,
        "all_wording_matches": all(r["wording_matches"] for r in rows),
    }
    immutable_json(output, result)
    if not result["all_wording_matches"]:
        raise ValueError("Provisional reference wording inconsistency")
    return result
