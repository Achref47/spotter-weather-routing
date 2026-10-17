"""A deterministic, simulated storm for the demo mode. Pure functions, no I/O, no network.

This module only invents *physical readings* (wind in mph, rain and snow in inches/hour). It does
not classify them: the normal risk engine (risk.assess, with the cargo-weight overrides) does that,
so the demo can never drift away from the real thresholds.

The storm is a function of the trip, not of the wall clock, so the same trip gives the same
numbers every time:
  - It is centred halfway along the fastest route.
  - Its timeline is anchored to when that route reaches the centre (half its duration): it builds
    over the RAMP_HOURS before that moment, holds for HOLD_HOURS, then fades over FADE_HOURS. The
    heatmap slider therefore shows it arriving and leaving, however long the trip is.
  - Intensity falls off linearly with distance from the centre, out to RADIUS_FRACTION of the
    route's end-to-end distance. A route that avoids the centre gets milder weather.
"""
import math
from dataclasses import dataclass

from .checkpoints import METERS_PER_MILE, haversine_m
from .risk import HEAVY_LOAD_NO_TRAVEL_LB, HEAVY_LOAD_SEVERE_LB
from .route_selection import resample
from .weather_match import HOUR_S, HourlySeries

STORM_ID = "storm"
LABEL = "SIMULATED STORM: demonstration weather, not a live forecast"

RAMP_HOURS = 3.0  # intensity climbs from 0 to 1 over this long...
LEAD_HOURS = 1.0  # ...finishing this long before the fastest route reaches the centre
HOLD_HOURS = 8.0  # stays at full strength this long after that
FADE_HOURS = 12.0  # then fades to calm over this long
RADIUS_FRACTION = 0.25
MIN_SCALE_M = 20_000.0
CALM_WIND_MPH = 10.0
METERS_PER_DEG_LAT = 111_320.0


@dataclass(frozen=True)
class Storm:
    center: tuple  # (lat, lon)
    scale_m: float  # end-to-end distance of the fastest route
    reach_hour: float  # hours after departure when the fastest route reaches the centre


def storm_for_route(coords, duration_s: float) -> Storm:
    """The storm for a trip, built from its fastest route's geometry and duration."""
    (lon0, lat0), (lon1, lat1) = coords[0], coords[-1]
    points = resample(coords, METERS_PER_MILE)
    return Storm(
        center=points[len(points) // 2],
        scale_m=max(haversine_m(lat0, lon0, lat1, lon1), MIN_SCALE_M),
        reach_hour=duration_s / 3600.0 / 2.0,
    )


def storm_intensity(hour: float, reach_hour: float) -> float:
    """0 to 1 for a number of hours after departure: builds, holds, then fades."""
    full_from = max(reach_hour - LEAD_HOURS, 1.0)
    ramp_from = max(full_from - RAMP_HOURS, 0.0)
    full_until = max(full_from, reach_hour) + HOLD_HOURS
    fade_until = full_until + FADE_HOURS
    if hour <= ramp_from:
        return 0.0
    if hour < full_from:
        return (hour - ramp_from) / (full_from - ramp_from)
    if hour <= full_until:
        return 1.0
    if hour < fade_until:
        return (fade_until - hour) / FADE_HOURS
    return 0.0


def _fields(severity: float, cold: float):
    """Physical readings for a severity between 0 (calm) and 1 (storm core)."""
    wind = CALM_WIND_MPH + 55.0 * severity
    rain = 1.3 * severity**1.5
    snow = 7.0 * severity * severity * cold  # only on the cold northern flank
    return wind, rain, snow


def _spatial(lat, lon, storm: Storm):
    """(closeness 0..1 to the storm centre, cold 0..1) for a location. Independent of the hour."""
    distance = haversine_m(lat, lon, storm.center[0], storm.center[1])
    closeness = max(0.0, 1.0 - distance / (RADIUS_FRACTION * storm.scale_m))
    north_m = (lat - storm.center[0]) * METERS_PER_DEG_LAT
    cold = min(1.0, max(0.0, north_m / (0.10 * storm.scale_m)))
    return closeness, cold


def storm_conditions(lat, lon, hour, storm: Storm):
    """(wind_mph, rain_in_hr, snow_in_hr) at a location, a number of hours after departure."""
    closeness, cold = _spatial(lat, lon, storm)
    return _fields(storm_intensity(hour, storm.reach_hour) * closeness, cold)


def demo_series(points, departure, last_time, storm: Storm):
    """One HourlySeries per (lat, lon), in the same order, covering departure-1h to last_time+1h.

    The series use the same shape as live Open-Meteo data, so weather matching, risk, stats,
    ranking and the heatmap treat them exactly like a live forecast.
    """
    departure_ts = departure.timestamp()
    first = int(math.floor(departure_ts / HOUR_S)) * HOUR_S - HOUR_S
    last = int(math.ceil(last_time.timestamp() / HOUR_S)) * HOUR_S + HOUR_S
    times = tuple(range(first, last + 1, HOUR_S))
    intensity = [storm_intensity((t - departure_ts) / HOUR_S, storm.reach_hour) for t in times]

    series = []
    for lat, lon in points:
        closeness, cold = _spatial(lat, lon, storm)
        readings = [_fields(i * closeness, cold) for i in intensity]
        series.append(
            HourlySeries(
                times=times,
                wind_mph=tuple(r[0] for r in readings),
                liquid_in_hr=tuple(r[1] for r in readings),
                snow_in_hr=tuple(r[2] for r in readings),
            )
        )
    return series


def describe() -> dict:
    """What the interface shows about the demo. The numbers come from the real risk constants."""
    return {
        "id": STORM_ID,
        "label": LABEL,
        "description": (
            "Simulated wind, rain and snow are laid over your real routes. No weather service "
            "is called. The same trip always gives the same result."
        ),
        "how_to_read": [
            "The storm is centred halfway along the fastest route and is at full strength when "
            f"that route reaches it. It builds over the {RAMP_HOURS:.0f} hours before, holds for "
            f"{HOLD_HOURS:.0f} hours, then fades. Use the heatmap slider to watch it arrive and "
            "leave.",
            "Only the weather readings are simulated. Every risk level is worked out by the same "
            "rules and cargo-weight overrides as a live analysis.",
            f"Wind of 45 to 54 mph is Severe for loads up to {HEAVY_LOAD_NO_TRAVEL_LB:,} lb but "
            f"No Travel above it, and 35 to 44 mph becomes Severe above {HEAVY_LOAD_SEVERE_LB:,} "
            "lb. Re-run with a lighter load to see the difference.",
            "A route with any No Travel stretch is never recommended while a route without one "
            "exists. If every route has one, the app says there is no safe route.",
        ],
    }
