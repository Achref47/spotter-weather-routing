from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from trips.errors import WeatherError
from trips.services import weather

B = 1_800_000_000


@pytest.fixture(autouse=True)
def fresh_cache():
    weather.clear_cache()
    yield
    weather.clear_cache()


def loc(wind=(10, 11), rain=(0.0, 0.1), showers=(0.0, 0.0), snow=(0.0, 0.5),
        wind_unit="mp/h", precip_unit="inch"):
    n = len(wind)
    return {
        "hourly_units": {
            "wind_speed_10m": wind_unit,
            "rain": precip_unit,
            "showers": precip_unit,
            "snowfall": precip_unit,
        },
        "hourly": {
            "time": [B + 3600 * i for i in range(n)],
            "wind_speed_10m": list(wind),
            "rain": list(rain),
            "showers": list(showers),
            "snowfall": list(snow),
        },
    }


def default_payload(n):
    locations = [loc() for _ in range(n)]
    return locations[0] if n == 1 else locations


class FakeResp:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f"{self.status} error")

    def json(self):
        return self.payload


def count_locations(url):
    return len(parse_qs(urlparse(url).query)["latitude"][0].split(","))


def patch_get(monkeypatch, payload=None, status=200, exc=None):
    urls = []

    def fake_get(url, **kwargs):
        urls.append(url)
        if exc:
            raise exc
        body = payload(count_locations(url)) if callable(payload) else payload
        return FakeResp(body, status)

    monkeypatch.setattr(weather.requests, "get", fake_get)
    return urls


def test_parses_two_locations_and_requests_mph_inch(monkeypatch):
    urls = patch_get(monkeypatch, default_payload)
    result = weather.series_for_points([(29.76, -95.37), (33.75, -84.39)], 3)
    assert len(result) == 2
    assert result[0].times == (B, B + 3600)
    assert result[0].wind_mph == (10.0, 11.0)
    assert result[0].snow_in_hr == (0.0, 0.5)
    assert len(urls) == 1
    for part in (
        "latitude=29.76,33.75",
        "longitude=-95.37,-84.39",
        "wind_speed_unit=mph",
        "precipitation_unit=inch",
        "timeformat=unixtime",
        "forecast_days=3",
    ):
        assert part in urls[0]


def test_single_location_response_is_an_object_not_a_list(monkeypatch):
    patch_get(monkeypatch, default_payload)
    result = weather.series_for_points([(29.76, -95.37)], 2)
    assert len(result) == 1
    assert result[0].wind_mph == (10.0, 11.0)


def test_liquid_is_rain_plus_showers(monkeypatch):
    patch_get(monkeypatch, loc(wind=(10,), rain=(0.2,), showers=(0.05,), snow=(0,)))
    result = weather.series_for_points([(29.76, -95.37)], 1)
    assert result[0].liquid_in_hr[0] == pytest.approx(0.25)


def test_null_values_stay_none(monkeypatch):
    patch_get(
        monkeypatch,
        loc(wind=(None, 5), rain=(None, 0.1), showers=(0.0, None), snow=(None, 0)),
    )
    series = weather.series_for_points([(29.76, -95.37)], 1)[0]
    assert series.wind_mph == (None, 5.0)
    assert series.liquid_in_hr == (None, None)
    assert series.snow_in_hr == (None, 0.0)


@pytest.mark.parametrize("bad", [loc(wind_unit="km/h"), loc(precip_unit="mm")])
def test_unexpected_units_are_rejected(monkeypatch, bad):
    patch_get(monkeypatch, bad)
    with pytest.raises(WeatherError, match="units"):
        weather.series_for_points([(29.76, -95.37)], 1)


def test_http_error_raises(monkeypatch):
    patch_get(monkeypatch, {}, status=503)
    with pytest.raises(WeatherError, match="unavailable"):
        weather.series_for_points([(29.76, -95.37)], 1)


def test_network_error_raises(monkeypatch):
    patch_get(monkeypatch, exc=requests.ConnectionError("down"))
    with pytest.raises(WeatherError, match="unavailable"):
        weather.series_for_points([(29.76, -95.37)], 1)


def test_location_count_mismatch_raises(monkeypatch):
    patch_get(monkeypatch, [loc()])  # one location returned for two requested
    with pytest.raises(WeatherError, match="Unexpected"):
        weather.series_for_points([(29.76, -95.37), (33.75, -84.39)], 1)


def test_missing_hourly_block_raises(monkeypatch):
    patch_get(monkeypatch, {"foo": 1})
    with pytest.raises(WeatherError, match="Unexpected"):
        weather.series_for_points([(29.76, -95.37)], 1)


def test_array_length_mismatch_raises(monkeypatch):
    patch_get(monkeypatch, loc(wind=(1, 2), rain=(0, 0), showers=(0,), snow=(0, 0)))
    with pytest.raises(WeatherError, match="Unexpected"):
        weather.series_for_points([(29.76, -95.37)], 1)


def test_requests_are_batched(monkeypatch):
    urls = patch_get(monkeypatch, default_payload)
    n = weather.BATCH_SIZE * 2 + 7
    points = [(20 + i * 0.1, -100.0) for i in range(n)]
    result = weather.series_for_points(points, 2)
    assert len(result) == n
    assert sorted(count_locations(u) for u in urls) == sorted(
        [weather.BATCH_SIZE, weather.BATCH_SIZE, 7]
    )


def test_nearby_points_share_one_location(monkeypatch):
    urls = patch_get(monkeypatch, default_payload)
    result = weather.series_for_points([(29.761, -95.372), (29.764, -95.368)], 1)
    assert len(urls) == 1
    assert "latitude=29.76&" in urls[0]
    assert result[0] is result[1]


def test_cache_hit_then_expiry(monkeypatch):
    urls = patch_get(monkeypatch, default_payload)
    clock = {"t": 0.0}
    monkeypatch.setattr(weather, "_now", lambda: clock["t"])
    points = [(29.76, -95.37)]
    weather.series_for_points(points, 2)
    clock["t"] = 100
    weather.series_for_points(points, 2)
    assert len(urls) == 1
    clock["t"] = weather.CACHE_TTL_S + 1
    weather.series_for_points(points, 2)
    assert len(urls) == 2


def test_cache_refetches_only_when_more_days_are_needed(monkeypatch):
    urls = patch_get(monkeypatch, default_payload)
    points = [(29.76, -95.37)]
    weather.series_for_points(points, 1)
    weather.series_for_points(points, 3)
    assert len(urls) == 2
    weather.series_for_points(points, 2)
    assert len(urls) == 2


@pytest.mark.parametrize(
    "last, expected",
    [
        (datetime(2026, 10, 16, 23, 30, tzinfo=timezone.utc), 1),
        (datetime(2026, 10, 18, 10, 0, tzinfo=timezone.utc), 3),
        (datetime(2026, 12, 31, 0, 0, tzinfo=timezone.utc), 16),
    ],
)
def test_forecast_days_for(last, expected):
    now = datetime(2026, 10, 16, 23, 0, tzinfo=timezone.utc)
    assert weather.forecast_days_for(last, now) == expected