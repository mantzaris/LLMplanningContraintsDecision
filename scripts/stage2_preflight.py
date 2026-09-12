#!/usr/bin/env python3
"""Offline, read-only protocol/annotation/universe checks before frozen pilot execution.

Reference annotations are read only here, never by the inference runner. No model calls.
"""

from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
import re
from plancheck.pilot_review import review_collection
from plancheck.prompts import prompt_manifest
from plancheck.runner import load_public, revision
from plancheck.util import digest, file_hash, immutable_json, read_json


def check(
    config: Path, protocol: Path, prepared: Path, references: Path, feed: Path, output: Path
) -> dict:
    settings, frozen = read_json(config), read_json(protocol)
    scenarios, pools = load_public(prepared / "public")
    data_manifest = read_json(prepared / "manifest.json")
    reference_rows = read_json(references)
    invariants = {
        "config": digest(settings) == frozen["config_hash"],
        "prompts": digest(prompt_manifest()) == frozen["prompt_hash"],
        "public": digest([s.model_dump(mode="json") for s in scenarios]) == frozen["public_hash"],
        "references": digest(reference_rows) == frozen["reference_hash"],
        "data_manifest": digest(data_manifest) == frozen["data_manifest_hash"],
        "feed": file_hash(feed) == data_manifest["data_config"]["feed_sha256"],
        "scenario_order": [s.scenario_id for s in scenarios] == settings["scenario_ids"],
        "unique_base_requests": len({s.base_id for s in scenarios}) == len(scenarios),
        "reference_ids": sorted(r["scenario_id"] for r in reference_rows)
        == sorted(settings["scenario_ids"]),
        "no_injected_errors": all(r["error_injection"] is False for r in reference_rows),
    }
    if not all(invariants.values()):
        raise ValueError(f"Frozen input mismatch: {invariants}")
    review = review_collection(prepared / "public", references, output / "annotation-review.json")
    prior_pairs = {tuple(pair) for pair in data_manifest["excluded_prior_OD_pairs"]}
    for scenario in scenarios:
        if scenario.split != "development":
            raise ValueError("Non-development scenario in pilot")
        endpoints = re.findall(r"\[stop_id=([^\]]+)\]", scenario.request)
        expected = [
            stop for segment in scenario.segments for stop in (segment.origin, segment.destination)
        ]
        if endpoints != expected or scenario.service_date not in scenario.request:
            raise ValueError(f"Request/public endpoint or date mismatch: {scenario.scenario_id}")
        if (scenario.segments[0].origin, scenario.segments[0].destination) in prior_pairs:
            raise ValueError("Prior OD pair reused")
        pool = pools[scenario.pool_hash]
        if len({j.journey_id for j in pool}) != len(pool):
            raise ValueError("Duplicate journey identity")
        for journey in pool:
            expected_scopes = [segment.scope for segment in scenario.segments]
            observed_scopes = list(dict.fromkeys(ride.scope for ride in journey.rides))
            if observed_scopes != expected_scopes:
                raise ValueError("Journey scope/order mismatch")
            for segment in scenario.segments:
                rides = [r for r in journey.rides if r.scope == segment.scope]
                if not (1 <= len(rides) <= scenario.max_rides_per_segment):
                    raise ValueError("Ride-count public bound violated")
                if (
                    rides[0].calls[0].stop_id != segment.origin
                    or rides[-1].calls[-1].stop_id != segment.destination
                ):
                    raise ValueError("Journey endpoint mismatch")
                if not segment.start_s <= rides[0].departure <= rides[-1].arrival <= segment.end_s:
                    raise ValueError("Journey outside public horizon")
                for left, right in zip(rides, rides[1:]):
                    if (
                        left.calls[-1].stop_id != right.calls[0].stop_id
                        or right.departure - left.arrival < scenario.minimum_connection_s
                    ):
                        raise ValueError("Invalid public connection")
                    if left.trip_id == right.trip_id:
                        raise ValueError("Repeated same-trip boarding")
            for left, right in zip(journey.rides, journey.rides[1:]):
                if left.arrival > right.departure:
                    raise ValueError("Nonchronological combined journey")
            for ride in journey.rides:
                if ride.route_id not in data_manifest["selected_routes"] or ride.mode != "bus":
                    raise ValueError("Unexpected route or mode in frozen bus-only subset")
                for call in ride.calls:
                    if call.stop_id not in scenario.stops or call.arrival_s > call.departure_s:
                        raise ValueError("Invalid stop identity or dwell timing")
                for left, right in zip(ride.calls, ride.calls[1:]):
                    if left.departure_s > right.arrival_s:
                        raise ValueError("Nonmonotonic scheduled calls")
    result = {
        "repository_revision": revision(),
        "protocol_hash": digest(frozen),
        "invariants": invariants,
        "scenario_count": len(scenarios),
        "journey_memberships_checked": sum(len(pools[s.pool_hash]) for s in scenarios),
        "public_pool_count": len(pools),
        "reference_feasible_count": sum(r["reference_feasible_count"] > 0 for r in review["rows"]),
        "reference_infeasible_count": sum(
            r["reference_feasible_count"] == 0 for r in review["rows"]
        ),
        "families": dict(Counter(r["family"] for r in reference_rows)),
        "universe_checks": "public request endpoints/date, scope/order, stop/trip identities, ride limits, chronological calls and connections, horizon, frozen routes/modes",
        "annotation_status": "provisional, automatically checked, not human audited",
        "annotation_issues": [],
        "protocol_amendments": [],
        "review_export_sha256": file_hash(protocol.parent / "annotation-review.csv"),
        "stage1_ledger_sha256": file_hash(Path("runs/stage1-gpu-budget.jsonl")),
        "stage2_ledger_sha256": file_hash(Path("runs/stage2-gpu-budget.jsonl")),
        "model_calls": 0,
    }
    immutable_json(output / "preflight.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/pilot.json"))
    parser.add_argument("--protocol", type=Path, default=Path("data/pilot/protocol.json"))
    parser.add_argument("--prepared", type=Path, default=Path("data/prepared/stage2"))
    parser.add_argument("--references", type=Path, default=Path("data/pilot/references.json"))
    parser.add_argument("--feed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = check(
        args.config, args.protocol, args.prepared, args.references, args.feed, args.output
    )
    print(
        {
            k: result[k]
            for k in (
                "scenario_count",
                "journey_memberships_checked",
                "reference_feasible_count",
                "reference_infeasible_count",
                "annotation_issues",
            )
        }
    )


if __name__ == "__main__":
    main()
