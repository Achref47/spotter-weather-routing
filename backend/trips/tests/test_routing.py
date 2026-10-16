import pytest
import requests

from trips.errors import RoutingError
from trips.services import routing

TOKEN = "pk.test-token-value"


def line(lat):
    return [[0.0, lat], [1.0, lat]]


def route(lat, duration):
    return {"distance_m": 111_000.0, "duration_s": float(duration), "coords": line(lat)}


class FakeResp:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def json(self):
        if self.payload is None:
            raise ValueError("no json")
        return self.payload


def mapbox_payload(*routes):
    return {
        "code": "Ok",
        "routes": [
            {
                "distance": r["distance_m"],
                "duration": r["duration_s"],
                "geometry": {"coordinates": r["coords"]},
            }
            for r in routes
        ],
    }


@pytest.fixture(autouse=True)
def token(monkeypatch):
    monkeypatch.setenv("MAPBOX_TOKEN", TOKEN)


def patch_get(monkeypatch, response=None, exc=None):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if exc:
            raise exc
        return response

    monkeypatch.setattr(routing.requests, "get", fake_get)
    return calls


def test_fetch_parses_routes_and_uses_lon_lat_order(monkeypatch):
    calls = patch_get(monkeypatch, FakeResp(mapbox_payload(route(0.0, 1000))))
    result = routing.fetch_routes([(29.76, -95.37), (33.75, -84.39)], alternatives=True)
    assert result[0]["duration_s"] == 1000.0
    url, kwargs = calls[0]
    assert url.endswith("/-95.37,29.76;-84.39,33.75")
    assert kwargs["params"]["alternatives"] == "true"


def test_missing_token_raises(monkeypatch):
    monkeypatch.delenv("MAPBOX_TOKEN", raising=False)
    with pytest.raises(RoutingError, match="not configured"):
        routing.fetch_routes([(0, 0), (1, 1)], alternatives=True)


def test_bad_credentials_raise(monkeypatch):
    patch_get(monkeypatch, FakeResp({"message": "Not Authorized"}, status=401))
    with pytest.raises(RoutingError, match="credentials"):
        routing.fetch_routes([(0, 0), (1, 1)], alternatives=True)


def test_no_route_raises(monkeypatch):
    patch_get(monkeypatch, FakeResp({"code": "NoRoute"}, status=422))
    with pytest.raises(RoutingError, match="No drivable route"):
        routing.fetch_routes([(0, 0), (1, 1)], alternatives=True)


def test_network_error_does_not_leak_token(monkeypatch):
    leaky = requests.ConnectionError(f"failed for https://api.mapbox.com/x?access_token={TOKEN}")
    patch_get(monkeypatch, exc=leaky)
    with pytest.raises(RoutingError) as info:
        routing.fetch_routes([(0, 0), (1, 1)], alternatives=True)
    assert TOKEN not in str(info.value)
    assert info.value.__cause__ is None


def test_empty_routes_raise(monkeypatch):
    patch_get(monkeypatch, FakeResp({"code": "Ok", "routes": []}))
    with pytest.raises(RoutingError, match="No drivable route"):
        routing.fetch_routes([(0, 0), (1, 1)], alternatives=True)


def fake_fetch(monkeypatch, responses):
    """responses: list consumed in order; an Exception instance is raised."""
    calls = []

    def fake(points, alternatives):
        calls.append(points)
        item = responses[len(calls) - 1]
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(routing, "fetch_routes", fake)
    return calls


OD = ({"lat": 0.0, "lon": 0.0}, {"lat": 0.0, "lon": 1.0})


def test_three_base_routes_need_no_fallback(monkeypatch):
    calls = fake_fetch(monkeypatch, [[route(0.0, 1000), route(1.0, 1100), route(0.5, 1200)]])
    result = routing.get_route_options(*OD)
    assert len(result) == 3
    assert len(calls) == 1


def test_fallback_fills_third_route_and_stops_when_full(monkeypatch):
    calls = fake_fetch(
        monkeypatch,
        [[route(0.0, 1000), route(1.0, 1100)], [route(0.5, 1200)], [route(-0.5, 1300)]],
    )
    result = routing.get_route_options(*OD)
    assert [r.label for r in result] == ["Fastest route", "Alternative route", "Alternate corridor"]
    assert len(calls) == 2  # base + one via request; the second via was not needed
    assert len(calls[1]) == 3  # origin, via point, destination


def test_fallback_failure_is_tolerated(monkeypatch):
    fake_fetch(
        monkeypatch,
        [[route(0.0, 1000)], RoutingError("boom"), [route(0.5, 1200)]],
    )
    result = routing.get_route_options(*OD)
    assert [r.label for r in result] == ["Fastest route", "Alternate corridor"]


def test_duplicate_fallback_route_is_dropped(monkeypatch):
    fake_fetch(
        monkeypatch,
        [[route(0.0, 1000)], [route(0.0, 1005)], [route(0.0, 1010)]],
    )
    result = routing.get_route_options(*OD)
    assert len(result) == 1


def test_base_failure_propagates(monkeypatch):
    fake_fetch(monkeypatch, [RoutingError("down")])
    with pytest.raises(RoutingError):
        routing.get_route_options(*OD)