import zipfile
from datetime import date, timedelta
from pathlib import Path
import pytest
from plancheck.gtfs import Feed, Network, seconds, service_instant
from plancheck.util import read_json
from conftest import ride


def make_feed(path):
    tables = {
        "agency.txt": "agency_id,agency_timezone\na,America/Los_Angeles\n",
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\nA,Alpha,45.51,-122.67\nB,Beta,45.52,-122.66\nC,Gamma,45.53,-122.65\n",
        "routes.txt": "route_id,route_type\nr,3\n",
        "trips.txt": "trip_id,service_id,route_id\nt,added,r\nt_removed,removed,r\n",
        "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nremoved,1,1,1,1,1,1,1,20260101,20261231\n",
        "calendar_dates.txt": "service_id,date,exception_type\nremoved,20260914,2\nadded,20260914,1\n",
        "stop_times.txt": "trip_id,stop_sequence,stop_id,arrival_time,departure_time,pickup_type,drop_off_type\nt,1,A,24:00:00,24:00:00,0,1\nt,2,B,24:10:00,24:11:00,1,0\nt,3,C,24:20:00,24:20:00,0,0\n",
        "transfers.txt": "from_stop_id,to_stop_id,transfer_type,min_transfer_time\nB,B,2,180\n",
    }
    with zipfile.ZipFile(path, "w") as z:
        for name, text in tables.items():
            z.writestr(name, text)
    return Feed(path)


def test_calendar_after_midnight_and_connection_rules(tmp_path):
    f = make_feed(tmp_path / "fixture.zip")
    assert f.active_services(date(2026, 9, 14)) == {"added"}
    assert f.active_services(date(2026, 9, 15)) == {"removed"}
    assert seconds("25:01:02") == 90062
    with pytest.raises(ValueError):
        seconds("24:60:00")
    bounds = {
        "bbox": [45.5, -122.69, 45.54, -122.64],
        "start_s": 86400,
        "end_s": 90000,
        "route_limit": 1,
        "minimum_connection_s": 120,
    }
    n = Network(f, date(2026, 9, 14), bounds)
    assert {r.trip_id for r in n.rides} == {"t"}
    assert not any(r.calls[0].stop_id == "B" for r in n.rides)
    assert any(r.arrival == 87600 for r in n.rides)
    first = ride("x", "A", "B", 100, 200)
    assert not n.connection_ok(first, ride("y", "B", "C", 379, 500))
    assert n.connection_ok(first, ride("y", "B", "C", 380, 500))
    n.transfer_index[("B", "B")] = [{"from_stop_id": "B", "to_stop_id": "B", "transfer_type": "3"}]
    assert not n.connection_ok(first, ride("y", "B", "C", 600, 700))


def test_dst_uses_noon_minus_twelve_elapsed_hours():
    day = date(2026, 3, 8)
    midnight = service_instant(day, 0, "America/Los_Angeles")
    noon = service_instant(day, 43200, "America/Los_Angeles")
    assert noon - midnight == timedelta(hours=12)
    assert noon.astimezone(__import__("zoneinfo").ZoneInfo("America/Los_Angeles")).hour == 12


def test_frozen_real_feed_calendar_and_extended_times():
    config = read_json(Path("configs/data.json"))
    path = Path("data/raw") / f"trimet-{config['feed_sha256']}.zip"
    if not path.exists():
        pytest.skip("acquire frozen public feed for this integration check")
    feed = Feed(path)
    exceptions = list(feed.rows("calendar_dates.txt"))
    assert exceptions
    for row in exceptions[:30]:
        day = date.fromisoformat(f"{row['date'][:4]}-{row['date'][4:6]}-{row['date'][6:]}")
        assert (row["service_id"] in feed.active_services(day)) == (row["exception_type"] == "1")
    assert any(
        row["arrival_time"] and seconds(row["arrival_time"]) >= 86400
        for row in feed.rows("stop_times.txt")
    )
