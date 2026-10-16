import pytest

from trips.domain.risk import (
    Level,
    assess,
    classify_rain,
    classify_snow,
    classify_wind,
    classify_wind_with_load,
)

L, M, H, S, N = Level.LOW, Level.MODERATE, Level.HIGH, Level.SEVERE, Level.NO_TRAVEL


@pytest.mark.parametrize(
    "mph, expected",
    [
        (0, L), (24.99, L), (25, M), (34.99, M), (35, H),
        (44.99, H), (45, S), (54.99, S), (55, N), (80, N),
    ],
)
def test_wind_boundaries(mph, expected):
    assert classify_wind(mph) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, L), (0.0999, L), (0.10, M), (0.1001, M),
        (0.2499, M), (0.25, H), (0.2501, H),
        (0.4999, H), (0.50, S), (0.5001, S),
        (0.9999, S), (1.00, S), (1.0001, N), (5, N),
    ],
)
def test_rain_boundaries(value, expected):
    assert classify_rain(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, L), (0.4999, L), (0.5, M), (0.5001, M),
        (0.9999, M), (1.0, H), (1.0001, H),
        (1.9999, H), (2.0, S), (2.0001, S),
        (2.9999, S), (3.0, S), (3.0001, N), (9, N),
    ],
)
def test_snow_boundaries(value, expected):
    assert classify_snow(value) == expected


@pytest.mark.parametrize(
    "mph, load, expected",
    [
        # Wind at or above 55 is No Travel for any load.
        (55, 0, N), (55, 30_000, N), (80, 80_000, N),
        # 45 to <55 mph: No Travel only when load is strictly above 30,000 lb.
        (45, 30_000, S), (45, 30_001, N), (50, 30_000, S), (50, 30_001, N),
        (54.99, 30_000, S), (54.99, 30_001, N), (45, 80_000, N),
        # 44.99 is outside the 30,000 lb rule.
        (44.99, 30_001, H),
        # 35 to <45 mph: Severe only when load is strictly above 40,000 lb.
        (35, 40_000, H), (35, 40_001, S), (40, 40_000, H), (40, 40_001, S),
        (44.99, 40_000, H), (44.99, 40_001, S),
        # 34.99 is outside the 40,000 lb rule.
        (34.99, 40_001, M), (34.99, 80_000, M),
        # The 30,000 lb rule wins over the 40,000 lb rule at 45 mph and above.
        (45, 40_001, N),
        # Lighter winds are never raised by load.
        (25, 80_000, M), (10, 80_000, L),
    ],
)
def test_wind_load_overrides(mph, load, expected):
    assert classify_wind_with_load(mph, load) == expected


def test_load_does_not_change_rain_or_snow():
    result = assess(0, 0.3, 1.5, 80_000)
    assert result.rain == H
    assert result.snow == H
    assert result.overall == H


def test_highest_factor_wins():
    result = assess(30, 0.3, 0.6, 0)  # Moderate, High, Moderate
    assert result.overall == H
    assert (result.wind, result.rain, result.snow) == (M, H, M)


def test_any_no_travel_factor_is_no_travel_overall():
    assert assess(10, 1.2, 0, 0).overall == N
    assert assess(10, 0, 3.5, 0).overall == N
    assert assess(55, 0, 0, 0).is_no_travel
    assert assess(50, 0, 0, 35_000).is_no_travel
    assert not assess(50, 0, 0, 30_000).is_no_travel


def test_load_override_is_explained_in_reasons():
    result = assess(40, 0, 0, 45_000)
    assert result.overall == S
    assert any("raised to Severe" in r for r in result.reasons)


def test_all_zero_is_complete_and_low():
    result = assess(0, 0, 0, 20_000)
    assert result.overall == L
    assert result.complete


def test_missing_values_are_not_treated_as_low():
    result = assess(None, None, None, 20_000)
    assert result.overall is None
    assert not result.complete


def test_partial_data_is_flagged_and_keeps_known_risk():
    result = assess(None, 0.3, 0, 0)
    assert result.overall == H
    assert not result.complete
    assert result.wind is None
    known_low = assess(None, 0, 0, 0)
    assert known_low.overall == L and not known_low.complete


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), -1, "abc"])
def test_invalid_readings_are_treated_as_missing(bad):
    result = assess(bad, 0, 0, 0)
    assert result.wind is None
    assert not result.complete


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), "abc", None])
def test_invalid_load_raises(bad):
    with pytest.raises(ValueError):
        assess(10, 0, 0, bad)


def test_floating_point_noise_does_not_break_boundaries():
    # 0.3 - 0.2 and 0.7 - 0.2 can come out a hair below 0.1 and 0.5 in floating point.
    assert assess(0, 0.3 - 0.2, 0, 0).rain == M
    assert assess(0, 0, 0.7 - 0.2, 0).snow == M
    assert assess(24.99999999999, 0, 0, 0).wind == M