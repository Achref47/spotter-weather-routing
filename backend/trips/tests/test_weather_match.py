from datetime import datetime, timezone

import pytest

from trips.domain.weather_match import HourlySeries, weather_at

B = 1_800_000_000  # a whole hour: 500000 * 3600


def make_series():
    return HourlySeries(
        times=(B, B + 3600, B + 7200),
        wind_mph=(10.0, 11.0, 12.0),
        liquid_in_hr=(0.0, 0.1, 0.2),
        snow_in_hr=(0.0, 0.5, 1.0),
    )


def at(offset_s):
    return datetime.fromtimestamp(B + offset_s, timezone.utc)


@pytest.mark.parametrize(
    "offset_s, wind, rain, snow",
    [
        (0, 10.0, 0.0, 0.0),  # exactly on the first hour
        (1200, 10.0, 0.1, 0.5),  # 20 min past: wind nearest hour, precip = hour ending at +1h
        (2400, 11.0, 0.1, 0.5),  # 40 min past: wind rounds up to the next hour
        (3600, 11.0, 0.1, 0.5),  # exactly on the second hour
        (8400, 12.0, None, None),  # 20 min past the last hour: precip hour not in series
        (-3600, None, None, None),  # before the series
        (-1200, 10.0, 0.0, 0.0),  # 20 min before the start
    ],
)
def test_matching_rules(offset_s, wind, rain, snow):
    result = weather_at(make_series(), at(offset_s))
    assert result == {"wind_mph": wind, "rain_in_hr": rain, "snow_in_hr": snow}


def test_missing_values_pass_through_as_none():
    series = HourlySeries(
        times=(B, B + 3600),
        wind_mph=(None, 5.0),
        liquid_in_hr=(None, 0.0),
        snow_in_hr=(0.0, None),
    )
    result = weather_at(series, at(1200))
    assert result["wind_mph"] is None
    assert result["rain_in_hr"] == 0.0
    assert result["snow_in_hr"] is None


def test_naive_datetime_is_rejected():
    with pytest.raises(ValueError):
        weather_at(make_series(), datetime(2026, 10, 20, 8, 0))


def test_mismatched_series_lengths_are_rejected():
    with pytest.raises(ValueError):
        HourlySeries(times=(B, B + 3600), wind_mph=(1.0,), liquid_in_hr=(0.0, 0.0), snow_in_hr=(0.0, 0.0))