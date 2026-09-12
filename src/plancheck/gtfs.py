"""Frozen GTFS acquisition, service-day parsing and conservative scheduled connections."""

from __future__ import annotations

import csv
import io
import shutil
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from .domain import Call, Journey, Ride, Segment
from .util import digest, file_hash, immutable_json, utc_now

SOURCE = "https://developer.trimet.org/schedule/gtfs.zip"
TERMS = "https://developer.trimet.org/terms_of_use.shtml"
MODES = {
    0: "tram",
    1: "subway",
    2: "rail",
    3: "bus",
    4: "ferry",
    5: "cable",
    6: "gondola",
    7: "funicular",
}


def seconds(value: str) -> int:
    fields = value.split(":")
    if len(fields) != 3 or any(not f.isdigit() for f in fields):
        raise ValueError(f"Invalid GTFS time: {value!r}")
    hours, minutes, secs = map(int, fields)
    if minutes >= 60 or secs >= 60:
        raise ValueError(f"Invalid GTFS time: {value!r}")
    return hours * 3600 + minutes * 60 + secs


def service_instant(day: date, value: int, agency_timezone: str) -> datetime:
    # GTFS time origin is local noon minus 12 elapsed hours, also on DST dates.
    noon = datetime.combine(day, datetime.min.time().replace(hour=12), ZoneInfo(agency_timezone))
    return noon.astimezone(timezone.utc) - timedelta(hours=12) + timedelta(seconds=value)


class Feed:
    def __init__(self, path: Path):
        self.path = path
        self.archive = zipfile.ZipFile(path)

    def rows(self, name: str):
        if name not in self.archive.namelist():
            return
        with self.archive.open(name) as binary:
            yield from csv.DictReader(io.TextIOWrapper(binary, encoding="utf-8-sig", newline=""))

    def active_services(self, day: date) -> set[str]:
        day_text = day.strftime("%Y%m%d")
        weekday = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")[
            day.weekday()
        ]
        active = {
            row["service_id"]
            for row in self.rows("calendar.txt")
            if row["start_date"] <= day_text <= row["end_date"] and row[weekday] == "1"
        }
        for row in self.rows("calendar_dates.txt"):
            if row["date"] == day_text:
                if row["exception_type"] == "1":
                    active.add(row["service_id"])
                elif row["exception_type"] == "2":
                    active.discard(row["service_id"])
                else:
                    raise ValueError("Invalid calendar exception_type")
        return active

    def metadata(self):
        return {
            "feed_info": list(self.rows("feed_info.txt")),
            "agencies": [
                {k: r.get(k) for k in ("agency_id", "agency_name", "agency_timezone")}
                for r in self.rows("agency.txt")
            ],
            "calendar_start": min(
                (r["start_date"] for r in self.rows("calendar.txt")), default=None
            ),
            "calendar_end": max((r["end_date"] for r in self.rows("calendar.txt")), default=None),
            "exception_start": min(
                (r["date"] for r in self.rows("calendar_dates.txt")), default=None
            ),
            "exception_end": max(
                (r["date"] for r in self.rows("calendar_dates.txt")), default=None
            ),
            "members": sorted(self.archive.namelist()),
        }


def acquire(
    raw_dir: Path, manifest_dir: Path, source: str = SOURCE, existing: Path | None = None
) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    temporary = existing or raw_dir / "download.part"
    headers = {}
    if existing is None:
        with (
            urllib.request.urlopen(source, timeout=120) as response,
            temporary.open("wb") as output,
        ):
            headers = {
                k: response.headers.get(k) for k in ("Last-Modified", "ETag", "Content-Length")
            }
            shutil.copyfileobj(response, output)
    checksum = file_hash(temporary)
    frozen = raw_dir / f"trimet-{checksum}.zip"
    if not frozen.exists():
        shutil.copyfile(temporary, frozen)
    feed = Feed(frozen)
    manifest = {
        "source": source,
        "source_page": "https://developer.trimet.org/GTFS.shtml",
        "retrieved_at": started,
        "retrieval_timestamp_definition": "acquisition start; existing import uses original file mtime as retrieval completion",
        "download_completed_at": datetime.fromtimestamp(
            temporary.stat().st_mtime, timezone.utc
        ).isoformat(),
        "sha256": checksum,
        "bytes": frozen.stat().st_size,
        "http_headers": headers,
        "reuse_terms": TERMS,
        "redistribution": "raw feed and derived schedules not committed; see docs/data.md",
        **feed.metadata(),
    }
    immutable_json(manifest_dir / f"trimet-{checksum}.json", manifest)
    return frozen


class Network:
    def __init__(self, feed: Feed, day: date, bounds: dict):
        self.feed = feed
        self.day = day
        self.bounds = bounds
        agencies = list(feed.rows("agency.txt"))
        timezones = {a["agency_timezone"] for a in agencies}
        if len(timezones) != 1:
            raise ValueError("unsupported: multiple agency time zones in one planning universe")
        self.timezone = next(iter(timezones))
        ZoneInfo(self.timezone)
        south, west, north, east = bounds["bbox"]
        self.stops = {
            r["stop_id"]: r
            for r in feed.rows("stops.txt")
            if r.get("stop_lat")
            and r.get("stop_lon")
            and south <= float(r["stop_lat"]) <= north
            and west <= float(r["stop_lon"]) <= east
            and r.get("location_type", "0") in {"", "0"}
        }
        self.routes = {r["route_id"]: r for r in feed.rows("routes.txt")}
        active = feed.active_services(day)
        frequency_trips = {r["trip_id"] for r in feed.rows("frequencies.txt")}
        self.trips = {
            r["trip_id"]: r
            for r in feed.rows("trips.txt")
            if r["service_id"] in active
            and r["trip_id"] not in frequency_trips
            and int(self.routes[r["route_id"]]["route_type"]) in MODES
        }
        times = defaultdict(list)
        for row in feed.rows("stop_times.txt"):
            if row["trip_id"] in self.trips:
                times[row["trip_id"]].append(row)
        route_stops = defaultdict(set)
        route_counts = defaultdict(int)
        self.times = {}
        self.exclusions = defaultdict(int)
        for trip_id, rows in times.items():
            rows.sort(key=lambda r: int(r["stop_sequence"]))
            if len({r["stop_sequence"] for r in rows}) != len(rows):
                raise ValueError("Duplicate trip stop_sequence")
            if any(not r.get("arrival_time") or not r.get("departure_time") for r in rows):
                self.exclusions["missing_times_trip"] += 1
                continue
            parsed = [(r, seconds(r["arrival_time"]), seconds(r["departure_time"])) for r in rows]
            if any(arr > dep for _, arr, dep in parsed) or any(
                a[2] > b[1] for a, b in zip(parsed, parsed[1:])
            ):
                raise ValueError(f"Nonmonotone stop times on trip {trip_id}")
            local = [
                r
                for r, arr, dep in parsed
                if r["stop_id"] in self.stops and bounds["start_s"] <= dep <= bounds["end_s"]
            ]
            if len(local) < 2:
                continue
            route_id = self.trips[trip_id]["route_id"]
            route_counts[route_id] += 1
            route_stops[route_id].update(r["stop_id"] for r in local)
            self.times[trip_id] = parsed
        # Freeze coverage rule before model outputs: busiest route, then maximum
        # shared stop coverage, trip count and lexicographic ID; exact-stop connected.
        rank = sorted(route_counts, key=lambda r: (-route_counts[r], r))
        if not rank:
            raise ValueError("No scheduled coverage in public bounds")
        selected = [rank[0]]
        connected_stops = set(route_stops[rank[0]])
        while len(selected) < bounds["route_limit"]:
            available = [r for r in rank if r not in selected and route_stops[r] & connected_stops]
            if not available:
                break
            chosen = min(
                available,
                key=lambda r: (-len(route_stops[r] & connected_stops), -route_counts[r], r),
            )
            selected.append(chosen)
            connected_stops.update(route_stops[chosen])
        self.selected_routes = selected
        self.transfers = list(feed.rows("transfers.txt"))
        self.transfer_index = defaultdict(list)
        for rule in self.transfers:
            self.transfer_index[(rule.get("from_stop_id", ""), rule.get("to_stop_id", ""))].append(
                rule
            )
        self.rides = []
        for trip_id, parsed in sorted(self.times.items()):
            trip = self.trips[trip_id]
            if trip["route_id"] not in selected:
                continue
            for start, (row, _, departure) in enumerate(parsed):
                if (
                    row["stop_id"] not in self.stops
                    or not bounds["start_s"] <= departure <= bounds["end_s"]
                ):
                    continue
                if row.get("pickup_type", "0") not in {"", "0"}:
                    continue
                for end in range(start + 1, len(parsed)):
                    last, arrival, _ = parsed[end]
                    if arrival > bounds["end_s"]:
                        break
                    if last["stop_id"] not in self.stops or last.get("drop_off_type", "0") not in {
                        "",
                        "0",
                    }:
                        continue
                    # All calls are retained, including any excursion outside bbox.
                    calls = tuple(
                        Call(stop_id=r["stop_id"], arrival_s=a, departure_s=d)
                        for r, a, d in parsed[start : end + 1]
                    )
                    self.rides.append(
                        Ride(
                            trip_id=trip_id,
                            route_id=trip["route_id"],
                            mode=MODES[int(self.routes[trip["route_id"]]["route_type"])],
                            calls=calls,
                        )
                    )
        # Names for every rendered call; no geographic omission in witness rendering.
        all_stops = {r["stop_id"]: r for r in feed.rows("stops.txt")}
        self.names = {
            c.stop_id: all_stops[c.stop_id]["stop_name"] for ride in self.rides for c in ride.calls
        }

    def connection_ok(self, left: Ride, right: Ride) -> bool:
        if left.trip_id == right.trip_id or left.calls[-1].stop_id != right.calls[0].stop_id:
            return False
        minimum = self.bounds["minimum_connection_s"]
        matching = []
        stop = left.calls[-1].stop_id
        for row in [
            rule
            for key in ((stop, stop), (stop, ""), ("", stop), ("", ""))
            for rule in self.transfer_index[key]
        ]:
            fields = {
                "from_stop_id": left.calls[-1].stop_id,
                "to_stop_id": right.calls[0].stop_id,
                "from_route_id": left.route_id,
                "to_route_id": right.route_id,
                "from_trip_id": left.trip_id,
                "to_trip_id": right.trip_id,
            }
            if all(not row.get(key) or row[key] == value for key, value in fields.items()):
                # GTFS precedence: both trips > trip/route > one trip > both routes > one route > stops.
                trips = sum(bool(row.get(k)) for k in ("from_trip_id", "to_trip_id"))
                routes = sum(bool(row.get(k)) for k in ("from_route_id", "to_route_id"))
                specificity = (
                    6
                    if trips == 2
                    else 5
                    if trips and routes
                    else 4
                    if trips
                    else 3
                    if routes == 2
                    else 2
                    if routes
                    else 1
                )
                matching.append((specificity, row))
        if matching:
            highest = max(x[0] for x in matching)
            for _, row in (x for x in matching if x[0] == highest):
                kind = row.get("transfer_type", "0") or "0"
                if kind in {"1", "3", "4", "5"}:
                    return False
                if kind == "2":
                    minimum = max(minimum, int(row["min_transfer_time"]))
                elif kind != "0":
                    raise ValueError("Unsupported transfer type")
        return right.departure >= left.arrival + minimum

    def pool(self, segments: tuple[Segment, ...]) -> tuple[list[Journey], dict]:
        segment_paths = []
        limit = self.bounds["segment_pool_limit"]
        counts = []
        for segment in segments:
            by_origin = defaultdict(list)
            for ride in self.rides:
                if segment.start_s <= ride.departure and ride.arrival <= segment.end_s:
                    by_origin[ride.calls[0].stop_id].append(ride)
            for rides in by_origin.values():
                rides.sort(key=lambda r: (r.departure, r.arrival, r.trip_id, r.calls[-1].stop_id))
            paths = []

            def search(path: tuple[Ride, ...], stop: str):
                if path and stop == segment.destination:
                    paths.append(path)
                    return
                if len(path) >= self.bounds["max_rides_per_segment"]:
                    return
                for ride in by_origin[stop]:
                    if path and not self.connection_ok(path[-1], ride):
                        continue
                    if any(previous.trip_id == ride.trip_id for previous in path):
                        continue
                    search(
                        path + (ride.model_copy(update={"scope": segment.scope}),),
                        ride.calls[-1].stop_id,
                    )

            search((), segment.origin)
            counts.append(len(paths))
            # Hash sampling across enumerated paths avoids only retaining earliest departures.
            paths.sort(key=lambda p: digest([r.model_dump(mode="json") for r in p]))
            segment_paths.append(paths[:limit])
        combined = [()]
        for paths in segment_paths:
            combined = [
                before + after
                for before in combined
                for after in paths
                if not before or before[-1].arrival <= after[0].departure
            ]
        journeys = [
            Journey(journey_id=digest([r.model_dump(mode="json") for r in rides])[:20], rides=rides)
            for rides in combined
        ]
        journeys.sort(key=lambda j: j.journey_id)
        cap = self.bounds["joint_pool_limit"]
        return journeys[:cap], {
            "segment_enumerated": counts,
            "joint_before_cap": len(journeys),
            "pool_size": min(cap, len(journeys)),
            "complete": all(n <= limit for n in counts) and len(journeys) <= cap,
        }
