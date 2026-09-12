"""Pre-outcome coverage sampling and provisional Stage 2 reference construction."""

from __future__ import annotations
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
import csv
from .domain import PublicScenario, Segment, objective
from .gtfs import Feed, Network
from .prepare import reference_rule
from .util import canonical, digest, file_hash, immutable_json, read_json

FAMILIES = ("timing", "transfers", "mode_exclusion", "scope", "ordered_visits", "infeasible")


def clock_text(seconds: int) -> str:
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def prepare_pilot(feed: Path, config: dict, prior_public: Path, destination: Path) -> dict:
    if file_hash(feed) != config["feed_sha256"]:
        raise ValueError("Frozen feed checksum mismatch")
    network = Network(Feed(feed), date.fromisoformat(config["service_date"]), config)
    prior = read_json(prior_public)
    excluded = {(s["origin"], s["destination"]) for row in prior for s in row["segments"]}
    excluded |= {(b, a) for a, b in excluded.copy()}
    pairs = defaultdict(list)
    for ride in network.rides:
        pair = (ride.calls[0].stop_id, ride.calls[-1].stop_id)
        if len(ride.calls) >= 4 and pair not in excluded:
            pairs[pair].append(ride)
    route_of = {
        pair: min(
            Counter(r.route_id for r in rides),
            key=lambda r: (-sum(x.route_id == r for x in rides), r),
        )
        for pair, rides in pairs.items()
    }
    selected, usage = [], Counter()
    for index in range(48):
        route = network.selected_routes[index % len(network.selected_routes)]
        eligible = [p for p in pairs if p not in selected and route_of[p] == route]
        if not eligible:
            raise ValueError("Cannot satisfy predeclared 16 OD groups per selected route")
        pair = min(
            eligible,
            key=lambda p: (
                max(usage[p[0]], usage[p[1]]),
                usage[p[0]] + usage[p[1]],
                -len(pairs[p]),
                p,
            ),
        )
        selected.append(pair)
        usage.update(pair)
    public, refs, pool_rows, review_rows = [], [], [], []
    for index, pair in enumerate(selected):
        # Cycle within each route too: six families, eight base requests each.
        family = FAMILIES[(index // 3 + index % 3 * 2) % 6]
        base_id = f"pilot-{index:02d}"
        outbound = Segment(
            scope="outbound",
            origin=pair[0],
            destination=pair[1],
            start_s=config["start_s"],
            end_s=config["end_s"],
        )
        segments = (outbound,)
        prefix = (
            f"On {config['service_date']}, plan the outbound journey from "
            f"{network.names[pair[0]]} [stop_id={pair[0]}] to "
            f"{network.names[pair[1]]} [stop_id={pair[1]}]. "
        )
        if family == "scope":

            def distance(a, b):
                return sum(
                    abs(float(network.stops[a][key]) - float(network.stops[b][key]))
                    for key in ("stop_lat", "stop_lon")
                )

            returning = min(
                pairs, key=lambda p: (distance(p[0], pair[1]) + distance(p[1], pair[0]), p)
            )
            segments += (
                Segment(
                    scope="return",
                    origin=returning[0],
                    destination=returning[1],
                    start_s=32400,
                    end_s=config["end_s"],
                ),
            )
            prefix += (
                f"Also plan a return segment from {network.names[returning[0]]} "
                f"[stop_id={returning[0]}] to {network.names[returning[1]]} "
                f"[stop_id={returning[1]}] within 09:00:00–10:00:00. "
                "I handle movement between the outbound destination and return origin "
                "myself outside these journeys. "
            )
        pool, info = network.pool(segments)
        if not pool:
            raise ValueError(f"Empty preselected pool: {base_id}; do not silently replace")
        # Public deterministic anchor used only to construct requests and annotations.
        anchors = sorted(pool, key=objective)
        anchor = anchors[len(anchors) // 2]
        first = anchor.rides[0]
        outbound_rides = [r for r in anchor.rides if r.scope == "outbound"]
        outbound_arrival = outbound_rides[-1].arrival
        rule = reference_rule
        if family == "timing":
            text = (
                f"Depart no earlier than {clock_text(first.departure)} and arrive by "
                f"{clock_text(outbound_arrival)}, both inclusive."
            )
            clauses = [
                rule("earliest_departure", first.departure),
                rule("latest_arrival", outbound_arrival),
            ]
        elif family == "transfers":
            limit = (index // 6) % 2
            text = (
                f"Make at most {limit} transfers. Do not depart before "
                f"{clock_text(first.departure)}."
            )
            clauses = [rule("transfer_limit", limit), rule("earliest_departure", first.departure)]
        elif family == "mode_exclusion":
            text = (
                f"Do not use rail or tram. Depart no later than {clock_text(first.departure)}, "
                f"inclusive. Make at most {len(outbound_rides) - 1} transfers."
            )
            clauses = [
                rule("forbidden_modes", ["rail", "tram"]),
                rule("latest_departure", first.departure),
                rule("transfer_limit", len(outbound_rides) - 1),
            ]
        elif family == "scope":
            bound = next(r.departure for r in anchor.rides if r.scope == "return")
            # Alternate the direction of the transfer restriction, without changing the DSL.
            scope = "outbound" if index % 2 else "return"
            limit = sum(r.scope == scope for r in anchor.rides) - 1
            text = (
                f"On the {scope} segment only, make at most {limit} transfers. "
                f"On the return segment only, depart no earlier than {clock_text(bound)}."
            )
            clauses = [
                rule("transfer_limit", limit, scope),
                rule("earliest_departure", bound, "return"),
            ]
        elif family == "ordered_visits":
            stops = list(dict.fromkeys(c.stop_id for r in outbound_rides for c in r.calls))
            visits = stops[1:3]
            if len(visits) != 2 or pair[1] in visits:
                raise ValueError(f"No two intermediate calls in anchor: {base_id}")
            text = (
                f"Call at stop {visits[0]} and then stop {visits[1]}, in that order; "
                "remaining aboard counts. Use only buses."
            )
            clauses = [rule("ordered_calls", visits), rule("allowed_modes", ["bus"])]
        else:
            if index % 2:
                text = "Depart no earlier than 08:30:00 and arrive by 08:00:00, both inclusive."
                clauses = [rule("earliest_departure", 30600), rule("latest_arrival", 28800)]
            else:
                text = "Do not use buses."
                clauses = [rule("forbidden_modes", ["bus"])]
        data = [j.model_dump(mode="json") for j in pool]
        pool_hash = digest(data)
        immutable_json(destination / "public/pools" / f"{pool_hash}.json", data)
        scenario = PublicScenario(
            scenario_id=base_id,
            base_id=base_id,
            split="development",
            request=prefix + text,
            authorship="assistant-authored deterministic research request; not passenger data",
            service_date=config["service_date"],
            timezone=network.timezone,
            stops=network.names,
            segments=segments,
            pool_hash=pool_hash,
            feed_hash=config["feed_sha256"],
            max_rides_per_segment=config["max_rides_per_segment"],
            minimum_connection_s=config["minimum_connection_s"],
            pool_complete=info["complete"],
        )
        public.append(scenario.model_dump(mode="json"))
        reference = {"and": clauses}
        refs.append(
            {
                "scenario_id": base_id,
                "base_id": base_id,
                "family": family,
                "reference_version": "stage2-provisional-v1",
                "reference": reference,
                "review_status": "provisional_automatically_checked_not_human_audited",
                "error_injection": False,
                "anchor_id": anchor.journey_id,
            }
        )
        pool_rows.append(
            {
                "scenario_id": base_id,
                "family": family,
                "primary_route": route_of[pair],
                "pool_hash": pool_hash,
                "pool_size": len(pool),
                **info,
            }
        )
        review_rows.append(
            {
                "scenario_id": base_id,
                "request": scenario.request,
                "reference": canonical(reference),
                "review_status": "provisional_not_human_audited",
                "reviewer": "",
                "uncertain": "",
                "correction": "",
            }
        )
    immutable_json(destination / "public/scenarios.json", public)
    immutable_json(destination / "private/references.json", refs)
    review_path = destination / "private/annotation-review.csv"
    if not review_path.exists():
        with review_path.open("x", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(review_rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(review_rows)
    manifest = {
        "version": "stage2-provisional-v1",
        "data_config": config,
        "public_hash": digest(public),
        "reference_hash": digest(refs),
        "prior_public_hash": digest(prior),
        "excluded_prior_OD_pairs": sorted(excluded),
        "scenario_ids": [s["scenario_id"] for s in public],
        "pools": pool_rows,
        "route_counts": dict(Counter(x["primary_route"] for x in pool_rows)),
        "family_counts": dict(Counter(x["family"] for x in pool_rows)),
        "endpoint_reuse": dict(usage),
        "selected_routes": network.selected_routes,
        "stop_count": len(network.names),
        "ride_edges": len(network.rides),
    }
    immutable_json(destination / "manifest.json", manifest)
    return manifest
