from datetime import datetime, timezone

from trips.domain.heatmap import (
    HEATMAP_HOURS,
    UNKNOWN,
    build_heatmap,
    hourly_levels,
    sample_corridor,
)
from trips.domain.weather_match import HourlySeries

B = 1_800_000_000  # a whole hour
DEPART = datetime.fromtimestamp(B, timezone.utc)
TIMES = tuple(B + 3600 * i for i in range(60))


def series(wind=10.0, rain=0.0, snow=0.0):
    def col(value):
        return value if isinstance(value, tuple) else tuple(value for _ in TIMES)

    return HourlySeries(TIMES, col(wind), col(rain), col(snow))


def line(length_deg):
    return [[0.0, 0.0], [length_deg, 0.0]]  # runs along the equator


def test_sample_straight_line_includes_start_and_endpoint():
    points = sample_corridor([line(2.0)], step_mi=25)
    assert len(points) == 7  # miles 0, 25, ..., 125 plus the endpoint near mile 138
    assert points[0] == (0.0, 0.0)
    assert points[-1] == (0.0, 2.0)


def test_sample_dedupes_identical_routes():
    one = sample_corridor([line(2.0)], step_mi=25)
    two = sample_corridor([line(2.0), line(2.0)], step_mi=25)
    assert two == one


def test_sample_respects_the_cap_by_widening_spacing():
    points = sample_corridor([line(20.0)], step_mi=25, max_points=20)
    assert 2 <= len(points) <= 20


def test_sample_cap_of_one():
    assert len(sample_corridor([line(20.0)], step_mi=25, max_points=1)) == 1


def test_levels_calm_weather_is_low_for_all_49_hours():
    levels = hourly_levels(series(wind=10.0), DEPART, 20_000)
    assert len(levels) == HEATMAP_HOURS + 1
    assert set(levels) == {0}


def test_levels_apply_the_load_overrides():
    assert set(hourly_levels(series(wind=50.0), DEPART, 35_000)) == {4}  # heavy: No Travel
    assert set(hourly_levels(series(wind=50.0), DEPART, 30_000)) == {3}  # exactly 30,000: Severe


def test_levels_missing_data_is_unknown_not_low():
    nones = tuple(None for _ in TIMES)
    levels = hourly_levels(series(wind=nones, rain=nones, snow=nones), DEPART, 20_000)
    assert set(levels) == {UNKNOWN}


def test_slider_hour_maps_to_departure_plus_n_hours():
    wind = tuple(10.0 if i < 10 else 50.0 for i in range(60))  # storm arrives at hour 10
    levels = hourly_levels(series(wind=wind), DEPART, 35_000)
    assert levels[:10] == [0] * 10
    assert levels[10:] == [4] * 39


def test_build_heatmap_shape_and_legend():
    points = [(29.76123, -95.37123), (33.75, -84.39)]
    result = build_heatmap(points, [series(), series(wind=60.0)], DEPART, 20_000)
    assert result["hours"] == 48
    assert result["start_time"] == DEPART.isoformat()
    assert result["legend"]["4"] == "No Travel" and result["legend"]["-1"] == "Unknown"
    assert [p["lat"] for p in result["points"]] == [29.761, 33.75]
    assert all(len(p["levels"]) == 49 for p in result["points"])
    assert set(result["points"][0]["levels"]) == {0}
    assert set(result["points"][1]["levels"]) == {4}