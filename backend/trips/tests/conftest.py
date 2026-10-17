from datetime import datetime, timezone

import pytest
from django.core.cache import cache

from trips.domain.weather_match import HourlySeries
from trips.services import analysis


def calm_weather(points, forecast_days):
    start = int(datetime.now(timezone.utc).timestamp() // 3600 * 3600)
    times = tuple(start + 3600 * i for i in range(24 * 4))
    wind = tuple(10.0 for _ in times)
    zeros = tuple(0.0 for _ in times)
    series = HourlySeries(times, wind, zeros, zeros)
    return [series for _ in points]


@pytest.fixture(autouse=True)
def calm_weather_by_default(monkeypatch):
    monkeypatch.setattr(analysis, "series_for_points", calm_weather)


@pytest.fixture(autouse=True)
def no_throttling_unless_a_test_asks_for_it(settings):
    """Throttle history lives in the cache and every test posts from the same address, so each test
    starts clean with very high limits. test_throttle.py sets real, low limits itself."""
    cache.clear()
    settings.ANALYZE_THROTTLE_RATES = {"analyze_burst": "100000/min", "analyze_hour": "100000/hour"}
    yield
    cache.clear()
