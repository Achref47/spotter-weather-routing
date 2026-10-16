from datetime import datetime, timezone

import pytest

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