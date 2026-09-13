"""Pre-generation construction of fresh Stage 3 requests over the frozen GTFS feed."""

from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
import csv
from .domain import PublicScenario, Segment, objective
from .gtfs import Feed, Network
from .pilot_review import review_wording
from .prepare import reference_rule
from .reference import check_reference
from .render import clock_text
from .util import canonical, digest, file_hash, immutable_json, read_json

FAMILIES = ("timing", "latest", "transfers", "timing", "latest", "transfers", "scope", "infeasible")


def coverage(reference, pool):
    rules = reference["and"]
    vectors = [tuple(check_reference(r, j) for j in pool) for r in rules]
    return [
        {
            "rule": r,
            "accepted": sum(v),
            "rejected": len(pool) - sum(v),
            "conditional_exclusions": sum(
                not v[k] and all(w[k] for n, w in enumerate(vectors) if n != i)
                for k in range(len(pool))
            ),
        }
        for i, (r, v) in enumerate(zip(rules, vectors))
    ]


def requirement(family, pool):
    ordered = sorted(pool, key=objective)
    rule = reference_rule
    choices = []
    for j in ordered:
        out = [r for r in j.rides if r.scope == "outbound"]
        departure, arrival = out[0].departure, out[-1].arrival
        if family == "timing":
            text = f"Depart no earlier than {clock_text(departure)} and arrive by {clock_text(arrival)}, both inclusive."
            rules = [rule("earliest_departure", departure), rule("latest_arrival", arrival)]
        elif family == "latest":
            text = f"Depart no later than {clock_text(departure)}, inclusive."
            rules = [rule("latest_departure", departure)]
        elif family == "transfers":
            if len(out) != 1:
                continue
            text = f"Make at most 0 transfers. Do not depart before {clock_text(departure)}."
            rules = [rule("transfer_limit", 0), rule("earliest_departure", departure)]
        elif family == "scope":
            if len(out) != 1:
                continue
            returning = next(r.departure for r in j.rides if r.scope == "return")
            text = (
                "On the outbound segment only, make at most 0 transfers. "
                f"On the return segment only, depart no earlier than {clock_text(returning)}."
            )
            rules = [
                rule("transfer_limit", 0, "outbound"),
                rule("earliest_departure", returning, "return"),
            ]
        else:
            dep = sorted({x.rides[0].departure for x in pool})
            arr = sorted({x.rides[-1].arrival for x in pool})
            lower, upper = dep[3 * len(dep) // 4], arr[len(arr) // 4]
            if lower <= upper:
                return None
            text = f"Depart no earlier than {clock_text(lower)} and arrive by {clock_text(upper)}, both inclusive."
            rules = [rule("earliest_departure", lower), rule("latest_arrival", upper)]
        reference = {"and": rules}
        measured = coverage(reference, pool)
        feasible = sum(check_reference(reference, x) for x in pool)
        if all(
            c["accepted"] and c["rejected"] and c["conditional_exclusions"] for c in measured
        ) and bool(feasible) == (family != "infeasible"):
            choices.append((text, reference, measured, feasible))
        if family == "infeasible":
            break
    return choices[len(choices) // 2] if choices else None


def prepare(feed_path, destination):
    config = {
        **read_json(Path("configs/data.json")),
        "start_s": 36000,
        "end_s": 46800,
        "segment_pool_limit": 128,
        "joint_pool_limit": 256,
    }
    assert file_hash(feed_path) == config["feed_sha256"]
    network = Network(Feed(feed_path), date.fromisoformat(config["service_date"]), config)
    previous = read_json(Path("data/prepared/public/scenarios.json")) + read_json(
        Path("data/prepared/stage2/public/scenarios.json")
    )
    excluded = {(s["origin"], s["destination"]) for row in previous for s in row["segments"]}
    excluded |= {(b, a) for a, b in excluded.copy()}
    pair_rides = defaultdict(list)
    for ride in network.rides:
        p = (ride.calls[0].stop_id, ride.calls[-1].stop_id)
        if len(ride.calls) >= 4 and p not in excluded:
            pair_rides[p].append(ride)
    route_of = {
        p: min(
            Counter(r.route_id for r in rs), key=lambda x: (-sum(r.route_id == x for r in rs), x)
        )
        for p, rs in pair_rides.items()
    }
    used, endpoint_usage = set(), Counter()
    public, refs, audit, rejected = [], [], [], []
    for index in range(32):
        family = FAMILIES[index % 8]
        route = network.selected_routes[index % len(network.selected_routes)]
        options = sorted(
            (p for p in pair_rides if p not in used and route_of[p] == route),
            key=lambda p: (
                max(endpoint_usage[p[0]], endpoint_usage[p[1]]),
                endpoint_usage[p[0]] + endpoint_usage[p[1]],
                -len(pair_rides[p]),
                p,
            ),
        )
        selected = None
        for pair in options:
            segments = (
                Segment(
                    scope="outbound",
                    origin=pair[0],
                    destination=pair[1],
                    start_s=36000,
                    end_s=43200 if family == "scope" else 46800,
                ),
            )
            if family == "scope":

                def distance(a, b):
                    return sum(
                        abs(float(network.stops[a][k]) - float(network.stops[b][k]))
                        for k in ("stop_lat", "stop_lon")
                    )

                returning = min(
                    (p for p in pair_rides if p not in used and p != pair),
                    key=lambda p: (distance(p[0], pair[1]) + distance(p[1], pair[0]), p),
                )
                segments += (
                    Segment(
                        scope="return",
                        origin=returning[0],
                        destination=returning[1],
                        start_s=43200,
                        end_s=46800,
                    ),
                )
            pool, info = network.pool(segments)
            chosen = requirement(family, pool) if pool else None
            if chosen:
                selected = (pair, segments, pool, info, chosen)
                break
            rejected.append(
                {
                    "slot": index,
                    "family": family,
                    "OD": list(pair),
                    "reason": "no nonvacuous conditionally effective supported requirement in public pool",
                }
            )
        if selected is None:
            raise ValueError(f"Cannot fill frozen coverage slot {index}: {family}")
        pair, segments, pool, info, (text, reference, measured, feasible) = selected
        sid = f"sampling-{index:02d}"
        request = (
            f"On {config['service_date']}, plan the outbound journey from {network.names[pair[0]]} "
            f"[stop_id={pair[0]}] to {network.names[pair[1]]} [stop_id={pair[1]}]. "
        )
        if family == "scope":
            r = segments[1]
            request += (
                f"Also plan a return segment from {network.names[r.origin]} [stop_id={r.origin}] to "
                f"{network.names[r.destination]} [stop_id={r.destination}] within 12:00:00–13:00:00. "
                "I handle movement between the outbound destination and return origin myself outside these journeys. "
            )
        request += text
        assert review_wording(request) == reference
        data = [j.model_dump(mode="json") for j in pool]
        pool_hash = digest(data)
        immutable_json(destination / "public/pools" / f"{pool_hash}.json", data)
        s = PublicScenario(
            scenario_id=sid,
            base_id=sid,
            split="development",
            request=request,
            authorship="assistant-authored constructed research request; not a passenger record",
            service_date=config["service_date"],
            timezone=network.timezone,
            stops=network.names,
            segments=segments,
            pool_hash=pool_hash,
            feed_hash=config["feed_sha256"],
            max_rides_per_segment=2,
            minimum_connection_s=120,
            pool_complete=info["complete"],
        )
        public.append(s.model_dump(mode="json"))
        refs.append(
            {
                "scenario_id": sid,
                "base_id": sid,
                "family": family,
                "reference": reference,
                "reference_version": "stage3-provisional-v1",
                "human_audited": False,
            }
        )
        audit.append(
            {
                "scenario_id": sid,
                "family": family,
                "wording_matches": True,
                "human_audited": False,
                "feasible_journeys": feasible,
                "pool_size": len(pool),
                "clause_coverage": measured,
                "enumeration": info,
                "primary_route": route,
            }
        )
        for segment in segments:
            used.add((segment.origin, segment.destination))
            used.add((segment.destination, segment.origin))
            endpoint_usage.update((segment.origin, segment.destination))
        print(f"Prepared {sid} {family}; pool={len(pool)} feasible={feasible}", flush=True)
    immutable_json(destination / "public/scenarios.json", public)
    immutable_json(destination / "private/references.json", refs)
    immutable_json(destination / "private/review.json", audit)
    manifest = {
        "version": "stage3-provisional-v1",
        "data_config": config,
        "scenario_ids": [s["scenario_id"] for s in public],
        "public_hash": digest(public),
        "reference_hash": digest(refs),
        "family_counts": dict(Counter(r["family"] for r in refs)),
        "selected_routes": network.selected_routes,
        "stops": len(network.names),
        "ride_edges": len(network.rides),
        "prior_segment_OD_overlap": 0,
        "date_overlap": "same service day as Stage 2",
        "window_overlap": "Stage 2 07–10; Stage 3 10–13, endpoints may touch at 10:00",
        "entity_overlap": "same agency/geography; route and stop reuse; new OD groups are not independent populations",
        "excluded_prior_ODs": sorted(excluded),
        "coverage_rejections_before_model_outputs": rejected,
        "sampling_rule": "eight-slot family cycle, round-robin route, endpoint reuse then ride coverage then IDs; first conditionally effective request; deterministic middle eligible anchor",
        "rows": audit,
    }
    immutable_json(destination / "manifest.json", manifest)
    path = destination / "private/annotation-review.csv"
    if not path.exists():
        with path.open("x") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=[
                    "scenario_id",
                    "request",
                    "reference",
                    "review_status",
                    "human_reviewer",
                    "uncertain",
                    "correction",
                ],
            )
            writer.writeheader()
            for s, r in zip(public, refs):
                writer.writerow(
                    {
                        "scenario_id": s["scenario_id"],
                        "request": s["request"],
                        "reference": canonical(r["reference"]),
                        "review_status": "provisional developer/automated review",
                    }
                )
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--feed", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    prepare(args.feed, args.output)
