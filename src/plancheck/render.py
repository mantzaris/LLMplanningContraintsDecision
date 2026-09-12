"""Deterministic, source-only concrete journey rendering."""

from __future__ import annotations
from .domain import Journey, PublicScenario


def clock_text(value: int) -> str:
    return f"{value // 3600:02d}:{value % 3600 // 60:02d}:{value % 60:02d}"


def render_journey(journey: Journey, scenario: PublicScenario) -> str:
    lines = [
        f"Scheduled journey; service date {scenario.service_date}; agency time zone {scenario.timezone}.",
        "Times use GTFS service-day hours (24:xx means after midnight). Times are inclusive.",
        "Every scheduled call is shown. A visit means a scheduled call, including remaining aboard.",
        "Transfers count boardings minus one within each named segment; turnaround is not a transfer.",
    ]
    for segment in scenario.segments:
        rides = [r for r in journey.rides if r.scope == segment.scope]
        lines.append(
            f"Segment {segment.scope}: {segment.origin} to {segment.destination}; "
            f"{max(0, len(rides) - 1)} transfers."
        )
        for index, ride in enumerate(rides):
            lines.append(
                f"Boarding {index + 1}: mode {ride.mode}, route {ride.route_id}, trip {ride.trip_id}."
            )
            for call in ride.calls:
                lines.append(
                    f"  {scenario.stops.get(call.stop_id, call.stop_id)} [stop_id={call.stop_id}]: "
                    f"arrival {clock_text(call.arrival_s)}, departure {clock_text(call.departure_s)}."
                )
            if index:
                lines.append(
                    f"Connection wait: {ride.departure - rides[index - 1].arrival} seconds at the same stop."
                )
    return "\n".join(lines)
