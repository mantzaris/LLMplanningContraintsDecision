"""Construct provisional requests separately from independent reference annotations."""

from __future__ import annotations
from collections import defaultdict
from datetime import date
from pathlib import Path
import csv
from .domain import PublicScenario, Segment
from .gtfs import Feed, Network
from .util import digest, file_hash, immutable_json, canonical


def reference_rule(requirement: str, target, direction: str = "outbound") -> dict:
    return {"requirement": requirement, "target": target, "direction": direction}


def prepare(feed_path: Path, config: dict, destination: Path) -> dict:
    checksum = file_hash(feed_path)
    if checksum != config["feed_sha256"]:
        raise ValueError("Frozen feed checksum mismatch")
    network = Network(Feed(feed_path), date.fromisoformat(config["service_date"]), config)
    pairs = defaultdict(list)
    for ride in network.rides:
        if len(ride.calls) >= 4:
            pairs[ride.calls[0].stop_id, ride.calls[-1].stop_id].append(ride)
    ranked = sorted(pairs, key=lambda pair: (-len(pairs[pair]), pair))
    # Group every request on the same OD and its return pair together. Distinct
    # endpoints reduce exact duplication; geography/routes still overlap.
    selected = []
    used = set()
    for pair in ranked:
        if pair[0] not in used and pair[1] not in used:
            selected.append(pair)
            used.update(pair)
        if len(selected) == config["base_groups"]:
            break
    if len(selected) < config["base_groups"]:
        raise ValueError("Insufficient OD coverage for predeclared groups")
    public = []
    references = []
    pool_manifest = []
    review = []
    for group, pair in enumerate(selected):
        base_id = f"g{group:02d}"
        split = "development" if group < 4 else "validation" if group == 4 else "held_out"
        outbound = Segment(
            scope="outbound",
            origin=pair[0],
            destination=pair[1],
            start_s=config["start_s"],
            end_s=config["end_s"],
        )
        # The return segment has explicit, independently public endpoints. Off-network
        # activity between segments is outside the transport task and stated in the request.
        return_pair = min(
            ranked,
            key=lambda p: (
                p != (pair[1], pair[0]),
                abs(
                    float(network.stops[p[0]]["stop_lat"])
                    - float(network.stops[pair[1]]["stop_lat"])
                )
                + abs(
                    float(network.stops[p[0]]["stop_lon"])
                    - float(network.stops[pair[1]]["stop_lon"])
                ),
                p,
            ),
        )
        returning = Segment(
            scope="return",
            origin=return_pair[0],
            destination=return_pair[1],
            start_s=32400,
            end_s=config["end_s"],
        )
        for two_segments in (False, True):
            segments = (outbound, returning) if two_segments else (outbound,)
            pool, info = network.pool(segments)
            if not pool:
                raise ValueError(f"Empty public scenario pool: {base_id}")
            pool_data = [j.model_dump(mode="json") for j in pool]
            pool_hash = digest(pool_data)
            immutable_json(destination / "public" / "pools" / f"{pool_hash}.json", pool_data)
            pool_manifest.append(
                {"base_id": base_id, "two_segments": two_segments, "pool_hash": pool_hash, **info}
            )
            prefix = (
                f"On {config['service_date']}, plan the outbound journey from "
                f"{network.names[pair[0]]} [stop_id={pair[0]}] to {network.names[pair[1]]} [stop_id={pair[1]}]. "
            )
            examples = []
            if two_segments:
                prefix += (
                    f"Also plan a return segment from {network.names[return_pair[0]]} "
                    f"[stop_id={return_pair[0]}] to {network.names[return_pair[1]]} "
                    f"[stop_id={return_pair[1]}] after 09:00:00. I handle any movement "
                    "between the outbound destination and return origin myself outside these journeys. "
                )
                examples = [
                    (
                        "scope",
                        "On the outbound segment only, make no transfers. "
                        "On the return segment, depart no earlier than 09:15:00.",
                        {
                            "and": [
                                reference_rule("transfer_limit", 0),
                                reference_rule("earliest_departure", 33300, "return"),
                            ]
                        },
                    )
                ]
            else:
                visit = pairs[pair][0].calls[1].stop_id
                second_visit = pairs[pair][0].calls[2].stop_id
                examples = [
                    (
                        "timing",
                        "Depart no earlier than 07:30:00 and arrive by 08:15:00, inclusive. Make at most one transfer.",
                        {
                            "and": [
                                reference_rule("earliest_departure", 27000),
                                reference_rule("latest_arrival", 29700),
                                reference_rule("transfer_limit", 1),
                            ]
                        },
                    ),
                    (
                        "negation",
                        "Do not use rail or tram. Do not depart before 07:45:00. Make no transfers.",
                        {
                            "and": [
                                reference_rule("forbidden_modes", ["rail", "tram"]),
                                reference_rule("earliest_departure", 27900),
                                reference_rule("transfer_limit", 0),
                            ]
                        },
                    ),
                    (
                        "visits",
                        f"Call at stop {visit} and then stop {second_visit}, in that order; remaining aboard counts. Use only buses.",
                        {
                            "and": [
                                reference_rule("ordered_calls", [visit, second_visit]),
                                reference_rule("allowed_modes", ["bus"]),
                            ]
                        },
                    ),
                    (
                        "infeasible",
                        "Depart no earlier than 08:30:00 and arrive by 08:00:00.",
                        {
                            "and": [
                                reference_rule("earliest_departure", 30600),
                                reference_rule("latest_arrival", 28800),
                            ]
                        },
                    ),
                ]
            for tag, requirement_text, reference in examples:
                for paraphrase in range(2):
                    request = prefix + requirement_text
                    if paraphrase:
                        request = "Please find scheduled transport for this request. " + request
                    identifier = f"{base_id}-{tag}-p{paraphrase}"
                    scenario = PublicScenario(
                        scenario_id=identifier,
                        base_id=base_id,
                        split=split,
                        request=request,
                        authorship="assistant-authored deterministic template; not passenger data",
                        service_date=config["service_date"],
                        timezone=network.timezone,
                        stops=network.names,
                        segments=segments,
                        pool_hash=pool_hash,
                        feed_hash=checksum,
                        max_rides_per_segment=config["max_rides_per_segment"],
                        minimum_connection_s=config["minimum_connection_s"],
                        pool_complete=info["complete"],
                    )
                    public.append(scenario.model_dump(mode="json"))
                    references.append(
                        {
                            "scenario_id": identifier,
                            "base_id": base_id,
                            "reference": reference,
                            "review_status": "provisional_unaudited",
                            "error_injection": False,
                        }
                    )
                    review.append(
                        {
                            "scenario_id": identifier,
                            "request": request,
                            "reference": canonical(reference),
                            "review_status": "provisional_unaudited",
                            "reviewer": "",
                            "correction": "",
                        }
                    )
    immutable_json(destination / "public" / "scenarios.json", public)
    immutable_json(destination / "private" / "references.json", references)
    review_path = destination / "private" / "annotation-review.csv"
    if not review_path.exists():
        with review_path.open("x", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(review[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(review)
    manifest = {
        "config": config,
        "config_hash": digest(config),
        "feed_hash": checksum,
        "route_selection": network.selected_routes,
        "selected_route_modes": {
            r: network.routes[r]["route_type"] for r in network.selected_routes
        },
        "stop_count": len(network.names),
        "ride_edges": len(network.rides),
        "exclusions": dict(network.exclusions),
        "scenario_count": len(public),
        "public_hash": digest(public),
        "reference_hash": digest(references),
        "pools": pool_manifest,
        "annotation_status": "assistant-authored provisional; not human audited",
    }
    immutable_json(destination / "manifest.json", manifest)
    return manifest
