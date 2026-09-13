#!/usr/bin/env python3
"""Fixed-pilot CPU closeout: audit annotations first, then rescore saved outputs.

No inference backend is instantiated; no candidates, journeys or new benchmark are
generated. Existing wording, reference, GTFS and outcome-checking tools are reused.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import io
from pathlib import Path
import re

from plancheck.constraints import parse_interpretation
from plancheck.gtfs import Feed, MODES, Network, seconds
from plancheck.pilot_analysis import classify, is_correct
from plancheck.pilot_review import review_wording
from plancheck.reference import check_reference
from plancheck.runner import load_public
from plancheck.util import canonical, digest, file_hash, immutable_json, read_json

START = "7e79d7c7f0e5b960313b1aa60969fa64f161ae36"
PUBLIC = Path("data/prepared/stage2/public")
REFERENCES = Path("data/pilot/references.json")
PRIOR = Path("artifacts/stage2/mechanism-v1")
RUN = Path("runs/stage2-pilot-v1")
OPERATORS = {
    "earliest_departure": ("depart_ge", "seconds"),
    "latest_departure": ("depart_le", "seconds"),
    "latest_arrival": ("arrive_by", "seconds"),
    "transfer_limit": ("max_transfers", "count"),
    "allowed_modes": ("permit_modes", "mode"),
    "forbidden_modes": ("exclude_modes", "mode"),
    "ordered_calls": ("visits", "stop_id"),
}


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text() != text:
            raise ValueError(f"Refusing changed artifact identity: {path}")
    else:
        path.write_text(text)


def write_csv(path, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(
        {k: canonical(v) if isinstance(v, (dict, list)) else v for k, v in row.items()}
        for row in rows
    )
    write_text(path, stream.getvalue())


def table(headers, rows):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")

    return "\n".join(
        ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
        + ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    )


def source_inventory(feed, config, pools):
    """Read the existing feed; do not enumerate new paths or select new data."""
    routes = {r["route_id"]: r for r in feed.rows("routes.txt")}
    trips = {t["trip_id"]: t for t in feed.rows("trips.txt")}
    stops = {s["stop_id"]: s for s in feed.rows("stops.txt")}
    day = date.fromisoformat(config["service_date"])
    active = feed.active_services(day)
    active_trips = {k: t for k, t in trips.items() if t["service_id"] in active}
    needed_trips = {r.trip_id for pool in pools.values() for j in pool for r in j.rides}
    selected_calls = defaultdict(list)
    window_trips, beyond_midnight = set(), set()
    local_calls = Counter()
    south, west, north, east = config["bbox"]
    bbox = {
        k
        for k, s in stops.items()
        if s.get("stop_lat")
        and s.get("stop_lon")
        and south <= float(s["stop_lat"]) <= north
        and west <= float(s["stop_lon"]) <= east
        and s.get("location_type", "0") in {"", "0"}
    }
    for row in feed.rows("stop_times.txt"):
        trip = row["trip_id"]
        if not row.get("arrival_time") or not row.get("departure_time"):
            continue
        arrival, departure = seconds(row["arrival_time"]), seconds(row["departure_time"])
        if trip in active_trips:
            if arrival >= 86400 or departure >= 86400:
                beyond_midnight.add(trip)
            if config["start_s"] <= departure <= config["end_s"]:
                window_trips.add(trip)
                if row["stop_id"] in bbox:
                    local_calls[trip] += 1
        if trip in needed_trips:
            selected_calls[trip].append(
                (
                    int(row["stop_sequence"]),
                    row["stop_id"],
                    arrival,
                    departure,
                    row.get("pickup_type", "0"),
                    row.get("drop_off_type", "0"),
                )
            )
    for rows in selected_calls.values():
        rows.sort()
    mode = {k: MODES[int(r["route_type"])] for k, r in routes.items()}
    source_counts = Counter(mode[k] for k in routes)
    active_counts = Counter(mode[t["route_id"]] for t in active_trips.values())
    window_counts = Counter(mode[trips[k]["route_id"]] for k in window_trips)
    eligible_routes = {trips[k]["route_id"] for k, n in local_calls.items() if n >= 2}
    selected_routes = {r.route_id for pool in pools.values() for j in pool for r in j.rides}
    # Reuse only the existing transfer validator, without Network.__init__/pool.
    connector = Network.__new__(Network)
    connector.bounds = config
    connector.transfer_index = defaultdict(list)
    for row in feed.rows("transfers.txt"):
        connector.transfer_index[(row.get("from_stop_id", ""), row.get("to_stop_id", ""))].append(
            row
        )
    invalid_rides = []
    seen_rides = set()
    for pool in pools.values():
        for journey in pool:
            for ride in journey.rides:
                key = digest(ride.model_dump(mode="json", exclude={"scope"}))
                if key in seen_rides:
                    continue
                seen_rides.add(key)
                calls = tuple((c.stop_id, c.arrival_s, c.departure_s) for c in ride.calls)
                source = selected_calls[ride.trip_id]
                matching = [
                    i
                    for i in range(len(source) - len(calls) + 1)
                    if tuple(r[1:4] for r in source[i : i + len(calls)]) == calls
                ]
                valid = (
                    ride.trip_id in active_trips
                    and trips[ride.trip_id]["route_id"] == ride.route_id
                    and mode[ride.route_id] == ride.mode
                    and any(
                        source[i][4] in {"", "0"} and source[i + len(calls) - 1][5] in {"", "0"}
                        for i in matching
                    )
                )
                if not valid:
                    invalid_rides.append(key)
    inventory = {
        "modes": [
            {
                "mode": m,
                "source_routes": source_counts[m],
                "active_trips_on_pilot_day": active_counts[m],
                "active_trips_with_a_07_10_departure": window_counts[m],
                "routes_with_two_bbox_window_calls": sum(mode[r] == m for r in eligible_routes),
                "selected_routes": sum(mode[r] == m for r in selected_routes),
            }
            for m in sorted(source_counts)
        ],
        "non_bus_routes": [
            {
                "route_id": k,
                "name": r["route_long_name"],
                "gtfs_route_type": int(r["route_type"]),
                "mode": mode[k],
            }
            for k, r in routes.items()
            if mode[k] != "bus"
        ],
        "active_service_ids": sorted(active),
        "exceptions_on_pilot_day": sum(
            r["date"] == day.strftime("%Y%m%d") for r in feed.rows("calendar_dates.txt")
        ),
        "active_trips_with_beyond_midnight_calls": len(beyond_midnight),
        "selected_routes": sorted(selected_routes),
        "unique_audited_rides": len(seen_rides),
        "invalid_ride_identities_or_calls": invalid_rides,
        "timezone": sorted({a["agency_timezone"] for a in feed.rows("agency.txt")}),
        "window_count_definition": "At least one departure in 07:00–10:00 on the active service day; not a journey count",
        "bbox_count_definition": "At least two in-bbox departure calls in that window on one active trip; eligibility only, not proof of usable OD alternatives",
    }
    return inventory, connector, stops


def audit(feed_path, output):
    config = read_json(Path("configs/data.json"))
    protocol = read_json(Path("data/pilot/protocol.json"))
    scenarios, pools = load_public(PUBLIC)
    references = read_json(REFERENCES)
    assert digest(references) == protocol["reference_hash"]
    assert digest(read_json(PUBLIC / "scenarios.json")) == protocol["public_hash"]
    assert file_hash(feed_path) == config["feed_sha256"]
    assert len(scenarios) == 48
    refs = {r["scenario_id"]: r for r in references}
    prior_review = {
        r["scenario_id"]: r for r in read_json(Path("data/pilot/automated-review.json"))["rows"]
    }
    ledgers = {str(p): file_hash(p) for p in sorted(Path("runs").glob("*budget*.jsonl"))}
    inventory, connector, feed_stops = source_inventory(Feed(feed_path), config, pools)
    annotations, clauses, capabilities, good_by_id = [], [], [], {}

    # This entire phase reads no method outputs, candidate bundles, or preferred plans.
    for scenario in scenarios:
        sid = scenario.scenario_id
        reference = refs[sid]["reference"]
        pool = pools[scenario.pool_hash]
        rules = reference["and"]
        reviewed = review_wording(scenario.request)
        # Expressibility check only: these reference-derived ASTs are never supplied
        # to a method, selected as predictions, or counted as generated candidates.
        probe = {
            "kind": "all",
            "children": [
                {
                    "kind": "atom",
                    "op": OPERATORS[r["requirement"]][0],
                    "scope": r["direction"],
                    "value": r["target"],
                    "unit": OPERATORS[r["requirement"]][1],
                }
                for r in rules
            ],
        }
        parse_interpretation(
            canonical({"status": "ok", "formula": probe, "unsupported": []}), scenario
        )
        identities = re.findall(r"\[stop_id=([^\]]+)\]", scenario.request)
        expected_ids = [v for s in scenario.segments for v in (s.origin, s.destination)]
        names_match = all(scenario.stops[k] == feed_stops[k]["stop_name"] for k in expected_ids)
        prefix_names = re.findall(
            r"(?:journey|segment) from (.*?) \[stop_id=[^\]]+\] to (.*?) \[stop_id=[^\]]+\]",
            scenario.request,
        )
        names_match &= [name for pair in prefix_names for name in pair] == [
            scenario.stops[k] for k in expected_ids
        ]
        date_ok = (
            scenario.request.startswith(f"On {scenario.service_date}, ")
            and scenario.service_date == config["service_date"]
        )
        timezone_ok = inventory["timezone"] == [scenario.timezone]
        window_ok = all(
            (s.start_s, s.end_s) == ((32400, 36000) if s.scope == "return" else (25200, 36000))
            for s in scenario.segments
        )
        if len(scenario.segments) > 1:
            window_ok &= "within 09:00:00–10:00:00" in scenario.request
            window_ok &= "myself outside these journeys" in scenario.request
        invalid_journeys = []
        for j in pool:
            valid = True
            for s in scenario.segments:
                rides = [r for r in j.rides if r.scope == s.scope]
                valid &= (
                    1 <= len(rides) <= scenario.max_rides_per_segment
                    and rides[0].calls[0].stop_id == s.origin
                    and rides[-1].calls[-1].stop_id == s.destination
                    and s.start_s <= rides[0].departure <= rides[-1].arrival <= s.end_s
                )
            valid &= all(
                connector.connection_ok(left, right)
                if left.scope == right.scope
                else left.arrival <= right.departure
                for left, right in zip(j.rides, j.rides[1:])
            )
            if not valid:
                invalid_journeys.append(j.journey_id)
        vectors = [tuple(check_reference(rule, j) for j in pool) for rule in rules]
        good = {j.journey_id for j in pool if check_reference(reference, j)}
        good_by_id[sid] = good
        row = {
            "scenario_id": sid,
            "family": refs[sid]["family"],
            "request": scenario.request,
            "reference_version": refs[sid]["reference_version"],
            "reference": reference,
            "wording_supports_reference": reviewed == reference,
            "times_units_inclusive_boundaries_agree": reviewed == reference,
            "date_timezone_agree": date_ok and timezone_ok,
            "endpoints_names_and_public_windows_agree": identities == expected_ids
            and names_match
            and window_ok,
            "scope_agrees": reviewed == reference,
            "visits_and_order_agree": reviewed == reference
            if any(r["requirement"] == "ordered_calls" for r in rules)
            else "not_applicable",
            "expressible": True,
            "pool_size": len(pool),
            "feasible_journeys": len(good),
            "feasibility_label_agrees": len(good) == prior_review[sid]["reference_feasible_count"],
            "invalid_public_journeys": invalid_journeys,
            "clear_reference_error": False,
            "unresolved_ambiguity": False,
            "audit_type": "developer/automated consistency audit; no independent human adjudication",
            "human_audited": False,
            "human_reviewer": "",
            "human_question": "",
            "human_correction": "",
        }
        assert all(
            row[k] is True
            for k in (
                "wording_supports_reference",
                "times_units_inclusive_boundaries_agree",
                "date_timezone_agree",
                "endpoints_names_and_public_windows_agree",
                "scope_agrees",
                "expressible",
                "feasibility_label_agrees",
            )
        ), sid
        assert not invalid_journeys, sid
        annotations.append(row)
        for index, (rule, vector) in enumerate(zip(rules, vectors)):
            n = sum(vector)
            equal = [i for i, v in enumerate(vectors) if i != index and v == vector]
            marginal = sum(
                not vector[k] and all(v[k] for i, v in enumerate(vectors) if i != index)
                for k in range(len(pool))
            )
            swap_count = None
            if len(scenario.segments) == 2:
                opposite = {
                    **rule,
                    "direction": "return" if rule["direction"] == "outbound" else "outbound",
                }
                swap_count = sum(
                    vector[k] != check_reference(opposite, j) for k, j in enumerate(pool)
                )
            equality = None
            if rule["requirement"] in {"earliest_departure", "latest_departure", "latest_arrival"}:
                equality = sum(
                    (
                        next(r for r in reversed(j.rides) if r.scope == rule["direction"]).arrival
                        if rule["requirement"] == "latest_arrival"
                        else next(r for r in j.rides if r.scope == rule["direction"]).departure
                    )
                    == rule["target"]
                    for j in pool
                )
            order_extra = None
            if rule["requirement"] == "ordered_calls":
                order_extra = sum(
                    set(rule["target"]).issubset(
                        {
                            c.stop_id
                            for r in j.rides
                            if r.scope == rule["direction"]
                            for c in r.calls
                        }
                    )
                    and not vector[k]
                    for k, j in enumerate(pool)
                )
            clauses.append(
                {
                    "scenario_id": sid,
                    "index": index,
                    "rule": rule,
                    "pool_size": len(pool),
                    "effect": "always_true"
                    if n == len(pool)
                    else "always_false"
                    if n == 0
                    else "separates",
                    "accepted": n,
                    "same_request_equivalent_clause_indices": equal,
                    "marginal_exclusions": marginal,
                    "direction_swap_changes_journeys": swap_count,
                    "exact_boundary_journeys": equality,
                    "ordering_exclusions_beyond_stop_presence": order_extra,
                    "unsupported_or_unreliable": False,
                }
            )
        segments = []
        for s in scenario.segments:
            paths = [[r for r in j.rides if r.scope == s.scope] for j in pool]
            segments.append(
                {
                    "scope": s.scope,
                    "transfer_values": sorted({len(p) - 1 for p in paths}),
                    "transfer_memberships": dict(
                        Counter(
                            "same_route" if left.route_id == right.route_id else "route_change"
                            for p in paths
                            for left, right in zip(p, p[1:])
                        )
                    ),
                    "distinct_stop_sets": len(
                        {tuple(sorted({c.stop_id for r in p for c in r.calls})) for p in paths}
                    ),
                    "distinct_call_sequences": len(
                        {tuple(c.stop_id for r in p for c in r.calls) for p in paths}
                    ),
                }
            )
        capabilities.append({"scenario_id": sid, "segments": segments})

    assert not inventory["invalid_ride_identities_or_calls"]
    # Persist the review before opening any outcome. With no corrections or unresolved
    # readings, there is no changed-reference/oracle replay and no case exclusion.
    immutable_json(output / "annotations.json", annotations)
    immutable_json(
        output / "corrections-v1.json",
        {
            "version": "stage2-closeout-reference-audit-v1",
            "original_reference_version": "stage2-provisional-v1",
            "original_reference_sha256": file_hash(REFERENCES),
            "corrections": [],
            "unresolved": [],
            "excluded_ids": [],
            "changed_reference_replay": "not applicable: zero corrections",
        },
    )
    immutable_json(
        output / "coverage.json",
        {"source": inventory, "clauses": clauses, "pool_capabilities": capabilities},
    )
    write_csv(output / "annotation-review.csv", annotations)
    write_csv(output / "constraint-coverage.csv", clauses)
    prior = read_json(PRIOR / "budget-outcomes.json")
    original = {
        (r["scenario_id"], r["method"], r["budget"]): r for r in prior if r["mode"] == "model"
    }
    rescored = []
    for scenario in scenarios:
        sid = scenario.scenario_id
        pair = read_json(RUN / "pairs" / f"{sid}-r0.json")
        for method, budget in [("A", 0), *[(m, b) for m in "DE" for b in (0, 1, 2, 4)]]:
            out = pair["secondary"]["A"] if method == "A" else pair["outputs"][method][str(budget)]
            category = classify(out, good_by_id[sid])
            old = original[(sid, method, budget)]
            assert category == old["category"], (sid, method, budget)
            rescored.append(
                {
                    "scenario_id": sid,
                    "method": method,
                    "budget": budget,
                    "original": old["category"],
                    "rescored": category,
                    "changed": False,
                }
            )
    immutable_json(output / "rescored-outputs.json", rescored)
    summary = {
        "starting_revision": START,
        "clear_annotation_errors": 0,
        "unresolved_annotation_cases": 0,
        "human_audited_cases": 0,
        "excluded_cases": 0,
        "requests_audited": len(annotations),
        "feasible_requests": sum(bool(r["feasible_journeys"]) for r in annotations),
        "rescored_outputs": len(rescored),
        "changed_categories": 0,
        "source_modes": inventory["modes"],
        "clause_effects": {},
        "direction_sensitive_clauses": [
            f"{c['scenario_id']}:{c['index']}"
            for c in clauses
            if c["direction_swap_changes_journeys"]
        ],
        "constraints_with_boundary_examples": sum(
            bool(c["exact_boundary_journeys"]) for c in clauses
        ),
        "two_transfer_journeys": sum(
            any(sum(r.scope == scope for r in j.rides) >= 3 for scope in {r.scope for r in j.rides})
            for pool in pools.values()
            for j in pool
        ),
        "requests_with_0_and_1_transfer_options": [
            c["scenario_id"]
            for c in capabilities
            if any(s["transfer_values"] == [0, 1] for s in c["segments"])
        ],
        "requests_with_different_stop_sets": [
            c["scenario_id"]
            for c in capabilities
            if any(s["distinct_stop_sets"] > 1 for s in c["segments"])
        ],
        "requests_with_route_changes": [
            c["scenario_id"]
            for c in capabilities
            if any(s["transfer_memberships"].get("route_change", 0) for s in c["segments"])
        ],
        "transfer_memberships": {
            kind: sum(
                s["transfer_memberships"].get(kind, 0) for c in capabilities for s in c["segments"]
            )
            for kind in ("same_route", "route_change")
        },
        "entire_request_always_satisfied": [
            r["scenario_id"] for r in annotations if r["feasible_journeys"] == r["pool_size"]
        ],
        "requests_where_order_adds_exclusions": [
            c["scenario_id"] for c in clauses if c["ordering_exclusions_beyond_stop_presence"]
        ],
        "new_gpu_generations": 0,
        "new_gpu_seconds": 0,
        "external_model_api_calls": 0,
        "disposition": "pause expansion of original consequence-weighting method; no retest justified by this audit",
    }
    for name in OPERATORS:
        cs = [c for c in clauses if c["rule"]["requirement"] == name]
        summary["clause_effects"][name] = {
            **{
                e: sum(c["effect"] == e for c in cs)
                for e in ("separates", "always_true", "always_false")
            },
            "duplicates_another_clause": sum(
                bool(c["same_request_equivalent_clause_indices"]) for c in cs
            ),
            "zero_marginal_exclusion": sum(c["marginal_exclusions"] == 0 for c in cs),
            "unsupported_or_unreliable": 0,
        }
    immutable_json(output / "summary.json", summary)
    tracked_inputs = [
        REFERENCES,
        PUBLIC / "scenarios.json",
        Path("configs/data.json"),
        Path("data/pilot/protocol.json"),
        Path("data/pilot/automated-review.json"),
        PRIOR / "budget-outcomes.json",
        PRIOR / "pool-sensitivity.json",
        Path("reports/STAGE2_MECHANISM_DIAGNOSIS.md"),
    ]
    assert ledgers == {p: file_hash(Path(p)) for p in ledgers}
    immutable_json(
        output / "provenance.json",
        {
            "starting_revision": START,
            "script_sha256": file_hash(Path(__file__)),
            "input_hashes": {str(p): file_hash(p) for p in tracked_inputs},
            "feed_sha256": config["feed_sha256"],
            "pool_hashes": sorted(pools),
            "gpu_ledger_hashes_unchanged": ledgers,
            "new_gpu_seconds": 0,
            "new_gpu_generations": 0,
            "external_model_api_calls": 0,
            "annotation_before_outcome_access": True,
            "replay_definition": "rescore saved ordinary outputs only; no selector rerun; unchanged-reference oracle results reused",
        },
    )
    annotation_table = table(
        ["ID", "Family", "Wording / time / scope", "Visits", "DSL", "Feasible / pool", "Issue"],
        [
            [
                r["scenario_id"],
                r["family"],
                "Agree",
                "Agree" if r["visits_and_order_agree"] is True else "—",
                "Supported",
                f"{r['feasible_journeys']}/{r['pool_size']}",
                "None identified",
            ]
            for r in annotations
        ],
    )
    family_table = table(
        [
            "Constraint",
            "Separates",
            "Always true",
            "Always false",
            "Duplicates*",
            "Zero marginal*",
            "Unsupported",
        ],
        [
            [
                name,
                c["separates"],
                c["always_true"],
                c["always_false"],
                c["duplicates_another_clause"],
                c["zero_marginal_exclusion"],
                c["unsupported_or_unreliable"],
            ]
            for name, c in summary["clause_effects"].items()
        ],
    )
    mode_table = table(
        [
            "GTFS mode",
            "Source routes",
            "Active trips",
            "Trips with morning call",
            "BBox-eligible routes",
            "Selected routes",
        ],
        [
            [
                r["mode"],
                r["source_routes"],
                r["active_trips_on_pilot_day"],
                r["active_trips_with_a_07_10_departure"],
                r["routes_with_two_bbox_window_calls"],
                r["selected_routes"],
            ]
            for r in inventory["modes"]
        ],
    )
    outcomes = []
    for method, budget in [("A", 0), *[("D = E", b) for b in (0, 1, 2, 4)]]:
        rs = [
            r
            for r in rescored
            if r["method"] == ("A" if method == "A" else "D") and r["budget"] == budget
        ]
        counts = Counter(r["rescored"] for r in rs)
        outcomes.append(
            [
                method,
                budget,
                f"{sum(is_correct(r['rescored']) for r in rs)}/48",
                counts["correct_feasible_plan"],
                counts["incorrect_plan"],
                counts["correct_infeasibility"],
                counts["false_infeasibility"],
                counts["invalid_model_output"],
                0,
            ]
        )
    results_table = table(
        [
            "Method",
            "Budget",
            "Original = rescored",
            "Valid plan",
            "Invalid plan",
            "Correct infeas.",
            "False infeas.",
            "Invalid output",
            "Unresolved / infra",
        ],
        outcomes,
    )
    write_text(
        output / "tables.md",
        "\n\n".join([annotation_table, family_table, mode_table, results_table]) + "\n",
    )
    print(canonical(summary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--feed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit(args.feed, args.output)
