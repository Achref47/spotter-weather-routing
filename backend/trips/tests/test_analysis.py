from datetime import datetime, timedelta, timezone

import pytest
from rest_framework.test import APIClient

from trips.domain.route_selection import Candidate
from trips.domain.weather_match import HourlySeries
from trips.errors import WeatherError
from trips.services import analysis

URL = "/api/trips/analyze"


def payload(load=42000):
    dep = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0)
    return {
        "origin": "Origin City",
        "destination": "Destination City",
        "departure_time": dep.isoformat(),
        "load_weight_lb": load,
        "checkpoint_interval_mi": 25,
    }


def cand(label, lat, duration):
    return Candidate(label, "alternative", 111_000.0, float(duration), [[0.0, lat], [1.0, lat]])


@pytest.fixture(autouse=True)
def two_routes(monkeypatch):
    monkeypatch.setattr(analysis, "geocode", lambda q: {"label": q, "lat": 0.0, "lon": 0.0})
    monkeypatch.setattr(
        analysis,
        "get_route_options",
        lambda o, d: [cand("Fastest route", 0.0, 3600), cand("Alternative route", 1.0, 4000)],
    )


def fake_weather(route1_wind=10.0, route2_wind=10.0, route2_missing=False):
    """Route 1 runs along latitude 0.0 and route 2 along latitude 1.0."""

    def fake(points, forecast_days):
        start = int(datetime.now(timezone.utc).timestamp() // 3600 * 3600)
        times = tuple(start + 3600 * i for i in range(24 * 4))
        zeros = tuple(0.0 for _ in times)
        out = []
        for lat, _lon in points:
            second = lat > 0.5
            if second and route2_missing:
                nones = tuple(None for _ in times)
                out.append(HourlySeries(times, nones, nones, nones))
            else:
                wind = route2_wind if second else route1_wind
                out.append(HourlySeries(times, tuple(wind for _ in times), zeros, zeros))
        return out

    return fake


def run(monkeypatch, fake, **kwargs):
    monkeypatch.setattr(analysis, "series_for_points", fake)
    return APIClient().post(URL, payload(**kwargs), format="json")


def test_calm_weather_is_all_low_and_fastest_route_wins(monkeypatch):
    resp = run(monkeypatch, fake_weather())
    assert resp.status_code == 200
    body = resp.json()
    for route in body["routes"]:
        assert all(c["risk"]["overall"] == "Low" for c in route["checkpoints"])
        assert route["summary"]["severe_mi"] == 0
    assert body["recommendation"]["route_id"] == "route-1"
    assert body["recommendation"]["status"] == "recommended"
    assert [r["rank"] for r in body["routes"]] == [1, 2]


def test_heavy_load_in_strong_wind_is_no_travel_and_route_is_excluded(monkeypatch):
    body = run(monkeypatch, fake_weather(route2_wind=50.0), load=42000).json()
    route2 = body["routes"][1]
    first = route2["checkpoints"][0]
    assert first["weather"]["wind_mph"] == 50.0
    assert first["risk"]["overall"] == "No Travel" and first["risk"]["overall_level"] == 4
    assert route2["summary"]["no_travel_mi"] == pytest.approx(route2["distance_mi"], abs=0.1)
    assert body["recommendation"]["route_id"] == "route-1"
    assert "No Travel" in body["recommendation"]["explanation"]


def test_same_wind_with_a_lighter_load_is_only_severe(monkeypatch):
    body = run(monkeypatch, fake_weather(route2_wind=50.0), load=30000).json()
    route2 = body["routes"][1]
    assert route2["checkpoints"][0]["risk"]["overall"] == "Severe"
    assert route2["summary"]["no_travel_mi"] == 0
    assert route2["summary"]["severe_mi"] == pytest.approx(route2["distance_mi"], abs=0.1)
    assert body["recommendation"]["route_id"] == "route-1"
    assert "Severe miles" in body["recommendation"]["explanation"]


def test_every_route_no_travel_means_no_safe_route(monkeypatch):
    body = run(monkeypatch, fake_weather(route1_wind=60.0, route2_wind=60.0)).json()
    assert body["recommendation"]["route_id"] is None
    assert body["recommendation"]["status"] == "no_safe_route"
    assert "No safe route" in body["recommendation"]["explanation"]
    assert len(body["routes"]) == 2
    assert [r["rank"] for r in body["routes"]] == [1, 2]


def test_missing_weather_is_unknown_not_low(monkeypatch):
    body = run(monkeypatch, fake_weather(route2_missing=True)).json()
    route2 = body["routes"][1]
    assert route2["summary"]["unknown_mi"] == pytest.approx(route2["distance_mi"], abs=0.1)
    assert route2["summary"]["avg_risk"] is None
    first = route2["checkpoints"][0]
    assert first["weather"]["wind_mph"] is None
    assert first["risk"]["overall"] is None and first["risk"]["complete"] is False
    assert body["recommendation"]["route_id"] == "route-1"
    assert body["recommendation"]["status"] == "incomplete_data"


def test_weather_failure_returns_422(monkeypatch):
    def boom(points, forecast_days):
        raise WeatherError("The weather service is unavailable.")

    resp = run(monkeypatch, boom)
    assert resp.status_code == 422
    assert "unavailable" in resp.json()["error"]


def test_summary_miles_add_up_to_the_route_length(monkeypatch):
    body = run(monkeypatch, fake_weather(route2_wind=38.0)).json()
    for route in body["routes"]:
        s = route["summary"]
        total = sum(s[k] for k in ("low_mi", "moderate_mi", "high_mi", "severe_mi",
                                   "no_travel_mi", "unknown_mi"))
        assert total == pytest.approx(route["distance_mi"], abs=0.3)


    

def test_heatmap_shape(monkeypatch):
    body = run(monkeypatch, fake_weather()).json()
    hm = body["heatmap"]
    assert hm["hours"] == 48
    assert hm["start_time"] == body["departure_time"]
    assert 2 <= len(hm["points"]) <= 80
    assert all(len(p["levels"]) == 49 for p in hm["points"])
    assert all(set(p["levels"]) == {0} for p in hm["points"])


def test_heatmap_marks_strong_wind_as_no_travel_where_it_blows(monkeypatch):
    body = run(monkeypatch, fake_weather(route2_wind=50.0), load=42000).json()
    points = body["heatmap"]["points"]
    second = [p for p in points if p["lat"] > 0.5]
    first = [p for p in points if p["lat"] <= 0.5]
    assert second and first
    assert all(set(p["levels"]) == {4} for p in second)
    assert all(set(p["levels"]) == {0} for p in first)