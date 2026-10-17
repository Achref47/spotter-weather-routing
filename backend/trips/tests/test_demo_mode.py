from datetime import datetime, timedelta, timezone

import pytest
from rest_framework.test import APIClient

from trips.domain import demo_weather
from trips.domain.route_selection import Candidate
from trips.services import analysis

URL = "/api/trips/analyze"
DEPARTURE = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0, second=0, minute=0)


def cand(label, lat, duration):
    # About 69 miles long, along a line of constant latitude.
    return Candidate(label, "alternative", 111_000.0, float(duration), [[0.0, lat], [1.0, lat]])


@pytest.fixture(autouse=True)
def two_routes(monkeypatch):
    """The fastest route runs through the storm centre; the alternative is about 111 km north."""
    monkeypatch.setattr(analysis, "geocode", lambda q: {"label": q, "lat": 0.0, "lon": 0.0})
    monkeypatch.setattr(
        analysis,
        "get_route_options",
        lambda o, d: [cand("Fastest route", 0.0, 6 * 3600), cand("Alternative route", 1.0, 6.5 * 3600)],
    )


def post(load=42_000, scenario="storm", **extra):
    body = {
        "origin": "Origin City",
        "destination": "Destination City",
        "departure_time": DEPARTURE.isoformat(),
        "load_weight_lb": load,
        "checkpoint_interval_mi": 10,
        **extra,
    }
    if scenario is not ...:
        body["demo_scenario"] = scenario
    return APIClient().post(URL, body, format="json")


def must_not_be_called(name):
    def boom(*args, **kwargs):
        raise AssertionError(f"{name} must not be used here")

    return boom


# --- isolation: the two weather sources never mix ------------------------------------------------

def test_demo_never_calls_the_live_weather_service(monkeypatch):
    monkeypatch.setattr(analysis, "series_for_points", must_not_be_called("live weather"))
    resp = post()
    assert resp.status_code == 200
    assert resp.json()["weather_source"] == "demo"


def test_live_analysis_never_uses_the_demo_generator(monkeypatch):
    monkeypatch.setattr(demo_weather, "demo_series", must_not_be_called("the demo generator"))
    for scenario in (..., None):  # field missing, or explicitly null
        body = post(scenario=scenario).json()
        assert body["weather_source"] == "live"
        assert body["demo"] is None
        assert not any("SIMULATED" in w for w in body["warnings"])


def test_unknown_scenario_is_rejected_not_silently_ignored():
    resp = post(scenario="tornado")
    assert resp.status_code == 400
    assert "demo_scenario" in resp.json()["details"]


def test_demo_is_labelled_in_the_response():
    body = post().json()
    assert "SIMULATED" in body["demo"]["label"]
    assert body["warnings"][0].startswith("SIMULATED STORM")
    assert len(body["demo"]["how_to_read"]) == 4


# --- the demo runs through the real risk, ranking and safety-gate logic --------------------------

def test_the_storm_makes_the_fastest_route_no_travel_and_the_safety_gate_excludes_it():
    body = post().json()
    fastest, alternative = body["routes"]
    assert fastest["summary"]["no_travel_mi"] > 0
    assert alternative["summary"]["no_travel_mi"] == 0
    rec = body["recommendation"]
    assert rec["route_id"] == alternative["id"]
    assert rec["status"] == "recommended"
    assert "excluded" in rec["explanation"]


def test_checkpoint_reasons_explain_why_a_stretch_is_no_travel():
    fastest = post().json()["routes"][0]
    no_travel = [c for c in fastest["checkpoints"] if c["risk"]["overall"] == "No Travel"]
    assert no_travel
    assert any("No Travel" in reason for c in no_travel for reason in c["risk"]["reasons"])


def test_a_lighter_load_turns_no_travel_into_severe_through_the_cargo_override():
    heavy = post(load=42_000).json()["routes"][0]["summary"]
    light = post(load=30_000).json()["routes"][0]["summary"]  # exactly 30,000 lb does not trigger it
    assert heavy["no_travel_mi"] > 0
    assert light["no_travel_mi"] == 0
    assert light["severe_mi"] > 0


def test_the_demo_heatmap_shows_the_storm_arriving_and_leaving():
    points = post().json()["heatmap"]["points"]
    near_centre = [p for p in points if p["lat"] <= 0.5 and 0.2 < p["lon"] < 0.8]
    assert near_centre
    for p in near_centre:
        assert p["levels"][0] == 0  # calm at departure
        assert p["levels"][-1] == 0  # calm again by hour 48
    # Heatmap points sit about 25 miles apart, so on this short 69-mile test route none lands on
    # the core. High or worse while the storm holds is what this geometry can show.
    assert max(max(p["levels"]) for p in near_centre) >= 2
    far = [p for p in points if p["lat"] > 0.5]
    assert far and all(max(p["levels"]) == 0 for p in far)  # the northern route stays calm


def test_when_every_route_crosses_the_storm_there_is_no_safe_route(monkeypatch):
    monkeypatch.setattr(
        analysis,
        "get_route_options",
        lambda o, d: [cand("Fastest route", 0.0, 6 * 3600)],  # one route, through the centre
    )
    rec = post().json()["recommendation"]
    assert rec["status"] == "no_safe_route" and rec["route_id"] is None


def test_the_demo_is_repeatable():
    first = post().json()
    second = post().json()
    for key in ("routes", "recommendation", "heatmap", "weather_source", "demo", "warnings"):
        assert first[key] == second[key]
