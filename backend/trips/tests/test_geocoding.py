import pytest
import requests

from trips.errors import GeocodingError
from trips.services import geocoding


class FakeResp:
    def __init__(self, payload=None, status=200):
        self.payload = payload
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f"{self.status} error")

    def json(self):
        return self.payload



REAL_THROTTLE = geocoding._throttle


@pytest.fixture(autouse=True)
def clear_cache(monkeypatch):
    geocoding._lookup.cache_clear()
    monkeypatch.setattr(geocoding, "_throttle", lambda: None)


def patch_get(monkeypatch, response=None, exc=None):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if exc:
            raise exc
        return response

    monkeypatch.setattr(geocoding.requests, "get", fake_get)
    return calls


HOUSTON = [{"lat": "29.7589", "lon": "-95.3677", "display_name": "Houston, Texas, USA"}]


def test_success_returns_floats_and_label(monkeypatch):
    patch_get(monkeypatch, FakeResp(HOUSTON))
    result = geocoding.geocode("Houston, TX")
    assert result == {"label": "Houston, Texas, USA", "lat": 29.7589, "lon": -95.3677}


def test_sends_user_agent_header(monkeypatch):
    calls = patch_get(monkeypatch, FakeResp(HOUSTON))
    geocoding.geocode("Houston")
    assert "spotter-weather-routing" in calls[0][1]["headers"]["User-Agent"]


def test_no_match_raises(monkeypatch):
    patch_get(monkeypatch, FakeResp([]))
    with pytest.raises(GeocodingError, match="No match"):
        geocoding.geocode("zzzzqqqq")


def test_http_error_raises(monkeypatch):
    patch_get(monkeypatch, FakeResp([], status=503))
    with pytest.raises(GeocodingError, match="unavailable"):
        geocoding.geocode("Houston")


def test_network_error_raises(monkeypatch):
    patch_get(monkeypatch, exc=requests.ConnectionError("down"))
    with pytest.raises(GeocodingError, match="unavailable"):
        geocoding.geocode("Houston")


def test_malformed_payload_raises(monkeypatch):
    patch_get(monkeypatch, FakeResp([{"display_name": "x"}]))
    with pytest.raises(GeocodingError, match="Unexpected"):
        geocoding.geocode("Houston")


def test_out_of_range_coordinates_raise(monkeypatch):
    patch_get(monkeypatch, FakeResp([{"lat": "95", "lon": "10", "display_name": "x"}]))
    with pytest.raises(GeocodingError, match="invalid"):
        geocoding.geocode("Nowhere")


@pytest.mark.parametrize("bad", ["", " ", "a", None])
def test_blank_query_rejected_without_network(monkeypatch, bad):
    calls = patch_get(monkeypatch, FakeResp(HOUSTON))
    with pytest.raises(GeocodingError):
        geocoding.geocode(bad)
    assert calls == []


def test_same_place_is_cached_ignoring_case_and_spacing(monkeypatch):
    calls = patch_get(monkeypatch, FakeResp(HOUSTON))
    geocoding.geocode("Houston,  TX")
    geocoding.geocode("houston, tx")
    assert len(calls) == 1

    

def test_throttle_spaces_out_real_lookups(monkeypatch):
    sleeps = []
    monkeypatch.setattr(geocoding.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(geocoding.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(geocoding, "_last_call", 99.5)
    REAL_THROTTLE()
    assert sleeps == [pytest.approx(0.5)]