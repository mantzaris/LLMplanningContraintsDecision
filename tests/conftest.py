import pytest
from plancheck.domain import Call, Journey, PublicScenario, Ride, Segment
from plancheck.util import digest


def ride(trip, origin, destination, departure, arrival, mode="bus", scope="outbound"):
    return Ride(
        trip_id=trip,
        route_id="r",
        mode=mode,
        scope=scope,
        calls=(
            Call(stop_id=origin, arrival_s=departure, departure_s=departure),
            Call(stop_id=destination, arrival_s=arrival, departure_s=arrival),
        ),
    )


@pytest.fixture
def pool():
    return [
        Journey(journey_id="a", rides=(ride("t1", "A", "C", 100, 200),)),
        Journey(
            journey_id="b",
            rides=(ride("t2", "A", "B", 120, 160), ride("t3", "B", "C", 170, 210, "tram")),
        ),
        Journey(journey_id="c", rides=(ride("t4", "A", "C", 150, 250, "tram"),)),
        Journey(journey_id="d", rides=(ride("t5", "A", "C", 200, 300),)),
    ]


@pytest.fixture
def scenario(pool):
    return PublicScenario(
        scenario_id="unit",
        base_id="unit",
        split="development",
        request="Depart no earlier than 150 seconds. Use only buses.",
        authorship="injected diagnostic fixture",
        service_date="2026-09-14",
        timezone="America/Los_Angeles",
        stops={"A": "Alpha", "B": "Beta", "C": "Gamma"},
        segments=(Segment(scope="outbound", origin="A", destination="C", start_s=0, end_s=400),),
        pool_hash=digest([j.model_dump(mode="json") for j in pool]),
        feed_hash="synthetic",
        max_rides_per_segment=2,
        minimum_connection_s=10,
    )
