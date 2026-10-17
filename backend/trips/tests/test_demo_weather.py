from datetime import datetime, timedelta, timezone

import pytest

from trips.domain import demo_weather as dw
from trips.domain.checkpoints import METERS_PER_MILE
from trips.domain.risk import Level, assess
from trips.domain.weather_match import weather_at

REACH = 6.0  # the fastest route reaches the storm centre 6 hours after departure
STORM = dw.Storm(center=(0.0, 0.5), scale_m=111_000.0, reach_hour=REACH)  # about 1 degree long
RADIUS = dw.RADIUS_FRACTION * STORM.scale_m
M_PER_DEG = 111_320.0
FULL_HOUR = 10.0  # between hour 5 and hour 14 the storm is at full strength


def at_distance(meters_east):
    """A point due east of the storm centre (same latitude, so no cold-air snow)."""
    return 0.0, 0.5 + meters_east / M_PER_DEG


def conditions(closeness, hour=FULL_HOUR):
    lat, lon = at_distance((1 - closeness) * RADIUS)
    return dw.storm_conditions(lat, lon, hour, STORM)


def risk_at(closeness, load_lb, hour=FULL_HOUR):
    """Risk from the real engine at a point whose storm closeness is `closeness` (0 to 1)."""
    return assess(*conditions(closeness, hour), load_lb)


# --- timeline -------------------------------------------------------------------------------------

def test_the_storm_is_deterministic():
    a = dw.storm_conditions(0.0, 0.62, 7.5, STORM)
    b = dw.storm_conditions(0.0, 0.62, 7.5, STORM)
    assert a == b


def test_intensity_builds_holds_and_fades():
    # reach 6 h: ramp from hour 2 to hour 5, full until hour 14, fade until hour 26
    f = lambda h: dw.storm_intensity(h, REACH)
    assert f(-3) == 0.0 and f(0) == 0.0 and f(2) == 0.0
    assert f(3.5) == pytest.approx(0.5)
    assert f(5) == 1.0 and f(REACH) == 1.0 and f(14) == 1.0
    assert f(20) == pytest.approx(0.5)
    assert f(26) == 0.0 and f(60) == 0.0


def test_a_short_trip_still_starts_calm_and_reaches_full_strength():
    # reach 1.5 h: the ramp is squeezed into the first hour instead of starting before departure
    f = lambda h: dw.storm_intensity(h, 1.5)
    assert f(0) == 0.0
    assert f(0.5) == pytest.approx(0.5)
    assert f(1) == 1.0 and f(1.5) == 1.0


def test_the_storm_is_at_full_strength_when_the_fastest_route_arrives():
    for reach in (1.0, 3.0, 6.0, 20.0):
        assert dw.storm_intensity(reach, reach) == 1.0
        assert dw.storm_intensity(0, reach) == 0.0  # always calm at departure


# --- the readings are classified by the real risk engine ------------------------------------------

def test_storm_core_is_no_travel_whatever_the_load():
    for load in (0, 30_000, 80_000):
        assert risk_at(1.0, load).overall == Level.NO_TRAVEL


def test_calm_before_departure_after_the_storm_and_far_away():
    assert risk_at(1.0, 80_000, hour=0).overall == Level.LOW
    assert risk_at(1.0, 80_000, hour=60).overall == Level.LOW
    lat, lon = at_distance(2 * RADIUS)
    wind, rain, snow = dw.storm_conditions(lat, lon, FULL_HOUR, STORM)
    assert (wind, rain, snow) == (dw.CALM_WIND_MPH, 0.0, 0.0)
    assert assess(wind, rain, snow, 80_000).overall == Level.LOW


def test_wind_45_to_54_is_severe_up_to_30000_lb_and_no_travel_above_it():
    assert 45 <= conditions(0.7)[0] < 55  # about 48.5 mph, inside the 45 to <55 band
    exact = risk_at(0.7, dw.HEAVY_LOAD_NO_TRAVEL_LB)
    heavy = risk_at(0.7, dw.HEAVY_LOAD_NO_TRAVEL_LB + 1)
    assert exact.wind == Level.SEVERE and exact.overall == Level.SEVERE
    assert heavy.wind == Level.NO_TRAVEL and heavy.overall == Level.NO_TRAVEL
    assert any("raised to No Travel" in r for r in heavy.reasons)


def test_wind_35_to_44_is_high_up_to_40000_lb_and_severe_above_it():
    assert 35 <= conditions(0.5)[0] < 45  # about 37.5 mph, inside the 35 to <45 band
    assert risk_at(0.5, dw.HEAVY_LOAD_SEVERE_LB).wind == Level.HIGH
    over = risk_at(0.5, dw.HEAVY_LOAD_SEVERE_LB + 1)
    assert over.wind == Level.SEVERE and over.overall == Level.SEVERE


def test_rain_alone_can_set_the_level():
    # closeness 0.25: wind is still Low (under 25 mph) but rain is Moderate
    result = risk_at(0.25, 80_000)
    assert result.wind == Level.LOW
    assert result.rain == Level.MODERATE
    assert result.overall == Level.MODERATE


def test_snow_appears_on_the_cold_northern_flank_only():
    # north of the centre the air is cold: 0.14 degrees is full cold, near the storm's edge
    wind, rain, snow = dw.storm_conditions(0.14, 0.5, FULL_HOUR, STORM)
    assert assess(wind, rain, snow, 0).snow == Level.HIGH
    nearer = dw.storm_conditions(0.10, 0.5, FULL_HOUR, STORM)
    assert assess(*nearer, 0).snow == Level.SEVERE
    south = dw.storm_conditions(-0.14, 0.5, FULL_HOUR, STORM)
    assert south[2] == 0.0


def test_the_demo_covers_every_level_from_low_to_no_travel():
    levels = {risk_at(c / 20, 42_000).overall for c in range(0, 21)}
    assert {Level.LOW, Level.MODERATE, Level.HIGH, Level.SEVERE, Level.NO_TRAVEL} <= levels


# --- series: same shape as live data --------------------------------------------------------------

def test_series_have_live_shape_cover_the_trip_and_have_no_gaps():
    departure = datetime(2026, 10, 18, 14, 30, tzinfo=timezone.utc)
    last = departure + timedelta(hours=60)
    series = dw.demo_series([(0.0, 0.5), (0.0, 0.9)], departure, last, STORM)
    assert len(series) == 2
    first = series[0]
    assert first.times[0] <= departure.timestamp() - 3600
    assert first.times[-1] >= last.timestamp() + 3600
    assert all(b - a == 3600 for a, b in zip(first.times, first.times[1:]))
    for s in series:
        values = s.wind_mph + s.liquid_in_hr + s.snow_in_hr
        assert all(v is not None for v in values)
        assert len(s.wind_mph) == len(s.liquid_in_hr) == len(s.snow_in_hr) == len(s.times)


def test_series_follow_the_same_matching_rules_as_live_data():
    departure = datetime(2026, 10, 18, 14, 0, tzinfo=timezone.utc)
    centre, far = dw.demo_series(
        [(0.0, 0.5), (0.0, 0.9)], departure, departure + timedelta(hours=60), STORM
    )
    peak = weather_at(centre, departure + timedelta(hours=10))
    assert peak["wind_mph"] == pytest.approx(dw.CALM_WIND_MPH + 55.0)
    assert weather_at(far, departure + timedelta(hours=10))["wind_mph"] == dw.CALM_WIND_MPH
    assert weather_at(centre, departure)["wind_mph"] == dw.CALM_WIND_MPH  # storm not here yet


def test_storm_is_a_function_of_the_trip_not_the_wall_clock():
    one = datetime(2026, 10, 18, 14, 0, tzinfo=timezone.utc)
    other = datetime(2026, 12, 1, 3, 0, tzinfo=timezone.utc)
    a = dw.demo_series([(0.0, 0.6)], one, one + timedelta(hours=50), STORM)[0]
    b = dw.demo_series([(0.0, 0.6)], other, other + timedelta(hours=50), STORM)[0]
    assert a.wind_mph == b.wind_mph and a.liquid_in_hr == b.liquid_in_hr


# --- building the storm from a route --------------------------------------------------------------

def test_storm_is_built_from_the_fastest_route():
    line = [[i / 100, 0.0] for i in range(101)]  # about 69 miles along the equator
    storm = dw.storm_for_route(line, duration_s=5 * 3600)
    assert storm.center[0] == pytest.approx(0.0, abs=1e-6)
    assert storm.center[1] == pytest.approx(0.5, abs=0.02)  # halfway along
    assert storm.scale_m == pytest.approx(111_195, rel=0.01)
    assert storm.reach_hour == pytest.approx(2.5)  # half the 5 hour duration


def test_scale_has_a_floor_for_tiny_or_looping_routes():
    storm = dw.storm_for_route([[0.0, 0.0], [0.0, 0.0]], duration_s=3600)
    assert storm.scale_m == dw.MIN_SCALE_M
    assert 100 * METERS_PER_MILE > dw.MIN_SCALE_M  # sanity: real routes are far above the floor


def test_description_is_clearly_labelled_and_quotes_the_real_load_limits():
    info = dw.describe()
    assert info["id"] == "storm"
    assert "SIMULATED" in info["label"] and "not a live forecast" in info["label"]
    text = " ".join(info["how_to_read"])
    assert "30,000" in text and "40,000" in text and "No Travel" in text
    assert len(info["how_to_read"]) == 4
