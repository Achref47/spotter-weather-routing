from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from trips.errors import WeatherError
from trips.services import weather

B = 1_800_000_000


def loc(wind=(10, 11)):
    return {
        "hourly_units": {
            "wind_speed_10m": "mp/h",
            "rain": "inch",
            "showers": "inch",
            "snowfall": "inch",
        },
        "hourly": {
            "time": [B, B + 3600],
            "wind_speed_10m": list(wind),
            "rain": [0.0, 0.0],
            "showers": [0.0, 0.0],
            "snowfall": [0.0, 0.0],
        },
    }


class OkResp:
    def __init__(self, payload=None):
        self.payload = loc() if payload is None else payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class Resp429:
    def raise_for_status(self):
        err = requests.HTTPError("429 error")
        err.response = SimpleNamespace(status_code=429, text="Too many requests")
        raise err

    def json(self):
        return {}


@pytest.fixture(autouse=True)
def quick_retries(monkeypatch):
    weather.clear_cache()
    monkeypatch.setattr(weather, "RETRY_DELAY_S", 0)
    yield
    weather.clear_cache()


def scripted(monkeypatch, outcomes):
    """Each call takes the next outcome; the last one repeats. Exceptions are raised."""
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        outcome = outcomes[min(len(calls), len(outcomes)) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(weather.requests, "get", fake_get)
    return calls


POINT = [(29.76, -95.37)]


def test_timeout_is_retried_once_then_succeeds(monkeypatch):
    calls = scripted(monkeypatch, [requests.ReadTimeout("slow"), OkResp()])
    result = weather.series_for_points(POINT, 1)
    assert len(result) == 1 and len(calls) == 2


def test_repeated_timeout_raises_after_one_retry(monkeypatch):
    calls = scripted(monkeypatch, [requests.ReadTimeout("slow")])
    with pytest.raises(WeatherError, match="unavailable"):
        weather.series_for_points(POINT, 1)
    assert len(calls) == 2


def test_rate_limit_is_retried_once_then_succeeds(monkeypatch):
    calls = scripted(monkeypatch, [Resp429(), OkResp()])
    assert len(weather.series_for_points(POINT, 1)) == 1
    assert len(calls) == 2


def test_repeated_rate_limit_gives_a_clear_message(monkeypatch):
    calls = scripted(monkeypatch, [Resp429()])
    with pytest.raises(WeatherError, match="rate limit"):
        weather.series_for_points(POINT, 1)
    assert len(calls) == 2


def test_plain_connection_error_is_not_retried(monkeypatch):
    calls = scripted(monkeypatch, [requests.ConnectionError("down")])
    with pytest.raises(WeatherError, match="unavailable"):
        weather.series_for_points(POINT, 1)
    assert len(calls) == 1


def test_parallel_batches_keep_the_input_order(monkeypatch):
    def fake_get(url, **kwargs):
        lats = [float(x) for x in parse_qs(urlparse(url).query)["latitude"][0].split(",")]
        items = [loc(wind=(lat, lat)) for lat in lats]
        return OkResp(items if len(items) > 1 else items[0])

    monkeypatch.setattr(weather.requests, "get", fake_get)
    points = [(20 + i * 0.1, -100.0) for i in range(60)]
    result = weather.series_for_points(points, 1)
    assert [s.wind_mph[0] for s in result] == [round(20 + i * 0.1, 2) for i in range(60)]