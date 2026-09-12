"""Public transport facts and the public, method-independent finite universe."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Mode = Literal["bus", "tram", "rail", "subway", "ferry", "cable", "gondola", "funicular"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Call(StrictModel):
    stop_id: str
    arrival_s: int
    departure_s: int


class Ride(StrictModel):
    trip_id: str
    route_id: str
    mode: Mode
    calls: tuple[Call, ...]
    scope: str = "outbound"

    @property
    def departure(self) -> int:
        return self.calls[0].departure_s

    @property
    def arrival(self) -> int:
        return self.calls[-1].arrival_s


class Journey(StrictModel):
    journey_id: str
    rides: tuple[Ride, ...]

    @model_validator(mode="after")
    def nonempty(self) -> Journey:
        if not self.rides or any(len(ride.calls) < 2 for ride in self.rides):
            raise ValueError("journeys must contain rides with at least two calls")
        return self


class Segment(StrictModel):
    scope: str
    origin: str
    destination: str
    start_s: int
    end_s: int


class PublicScenario(StrictModel):
    scenario_id: str
    base_id: str
    split: Literal["development", "validation", "held_out"]
    request: str
    authorship: str
    service_date: str
    timezone: str
    stops: dict[str, str]
    segments: tuple[Segment, ...]
    pool_hash: str
    feed_hash: str
    # These are PUBLIC infrastructure bounds, never inferred from request constraints.
    max_rides_per_segment: int = Field(ge=1)
    minimum_connection_s: int = Field(ge=0)
    pool_complete: bool = False


def objective(journey: Journey) -> tuple:
    """Earliest final arrival, fewest boardings, earliest departure, stable ID."""
    return (
        journey.rides[-1].arrival,
        len(journey.rides),
        journey.rides[0].departure,
        journey.journey_id,
    )
