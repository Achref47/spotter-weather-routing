from datetime import datetime, timedelta, timezone

import pytest
from rest_framework.test import APIClient

from trips.domain.route_selection import Candidate
from trips.errors import GeocodingError
from trips.services import analysis

URL = "/api/trips/analyze"


def utc_in(**delta):
    return (datetime.now(timezone.utc) + timedelta(**delta)).replace(microsecond=0)


def make_payload(**changes):
    body = {
        "origin": "Houston, TX",
        "destination": "Atlanta, GA",
        "departure_time": utc_in(days=1).isoformat(),
        "load_weight_lb": 42000,
    }
    for key, value in changes.items():
        if value is ...:
            body.pop(key, None)
        else:
            body[key] = value
    return body


def cand(label, lat, duration, source="alternative"):
    return Candidate(label, source, 111_000.0, float(duration), [[0.0, lat], [1.0, lat]])


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def fake_services(monkeypatch):
    monkeypatch.setattr(
        analysis,
        "geocode",
        lambda q: {"label": f"{q} (resolved)", "lat": 0.0, "lon": 0.0},
    )
    monkeypatch.setattr(
        analysis,
        "get_route_options",
        lambda o, d: [cand("Fastest route", 0.0, 3600), cand("Alternative route", 1.0, 4000)],
    )


def test_success_shape_and_etas(client, fake_services):
    dep = utc_in(days=1)
    resp = client.post(URL, make_payload(departure_time=dep.isoformat()), format="json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["origin"]["label"] == "Houston, TX (resolved)"
    route = body["routes"][0]
    assert route["id"] == "route-1"
    assert route["label"] == "Fastest route"
    assert route["geometry"]["type"] == "LineString"
    assert route["arrival_time"] == (dep + timedelta(hours=1)).isoformat()
    cps = route["checkpoints"]
    assert cps[0]["mile"] == 0 and cps[0]["eta"] == dep.isoformat()
    assert [round(c["mile"], 1) for c in cps] == [0, 25, 50, 69.0]  # default interval 25
    assert cps[-1]["eta"] == route["arrival_time"]


def test_offset_departure_is_converted_to_utc(client, fake_services):
    local = utc_in(days=1).astimezone(timezone(timedelta(hours=1)))
    resp = client.post(URL, make_payload(departure_time=local.isoformat()), format="json")
    assert resp.status_code == 200
    assert resp.json()["departure_time"] == local.astimezone(timezone.utc).isoformat()


def test_warning_when_fewer_than_three_routes(client, fake_services):
    resp = client.post(URL, make_payload(), format="json")
    assert "2 distinct route(s)" in resp.json()["warnings"][0]


@pytest.mark.parametrize(
    "changes, field",
    [
        ({"departure_time": utc_in(days=-1).isoformat()}, "departure_time"),
        ({"departure_time": utc_in(days=8).isoformat()}, "departure_time"),
        ({"departure_time": "2026-10-20T08:00:00"}, "departure_time"),
        ({"departure_time": "tomorrow"}, "departure_time"),
        ({"load_weight_lb": -1}, "load_weight_lb"),
        ({"load_weight_lb": 80001}, "load_weight_lb"),
        ({"load_weight_lb": "abc"}, "load_weight_lb"),
        ({"load_weight_lb": "nan"}, "load_weight_lb"),
        ({"checkpoint_interval_mi": 30}, "checkpoint_interval_mi"),
        ({"origin": "a"}, "origin"),
        ({"destination": ...}, "destination"),
    ],
)
def test_invalid_input_returns_400(client, fake_services, changes, field):
    resp = client.post(URL, make_payload(**changes), format="json")
    assert resp.status_code == 400
    assert field in resp.json()["details"]


def test_trip_error_returns_422(client, monkeypatch):
    def boom(query):
        raise GeocodingError("No match found for 'x'.")

    monkeypatch.setattr(analysis, "geocode", boom)
    resp = client.post(URL, make_payload(), format="json")
    assert resp.status_code == 422
    assert "No match" in resp.json()["error"]


def test_malformed_json_returns_400(client):
    resp = client.post(URL, "{not json", content_type="application/json")
    assert resp.status_code == 400


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}