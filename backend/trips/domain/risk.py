"""Weather risk classification for one checkpoint. Pure functions, no I/O.

Units: wind in mph, rain and snow in inches/hour, load in pounds.

Boundaries compare raw values. Lower bounds are inclusive and upper bounds are
exclusive, except the Severe upper bound for rain (1.00) and snow (3.0), which is
inclusive because No Travel is defined as strictly "above" those values.
"""
import math
from dataclasses import dataclass
from enum import IntEnum

HEAVY_LOAD_NO_TRAVEL_LB = 30_000  # with wind 45 to <55 mph: No Travel
HEAVY_LOAD_SEVERE_LB = 40_000  # with wind 35 to <45 mph: Severe


class Level(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()


def classify_wind(mph: float) -> Level:
    if mph >= 55:
        return Level.NO_TRAVEL
    if mph >= 45:
        return Level.SEVERE
    if mph >= 35:
        return Level.HIGH
    if mph >= 25:
        return Level.MODERATE
    return Level.LOW


def classify_rain(inches_per_hour: float) -> Level:
    if inches_per_hour > 1.00:
        return Level.NO_TRAVEL
    if inches_per_hour >= 0.50:
        return Level.SEVERE
    if inches_per_hour >= 0.25:
        return Level.HIGH
    if inches_per_hour >= 0.10:
        return Level.MODERATE
    return Level.LOW


def classify_snow(inches_per_hour: float) -> Level:
    if inches_per_hour > 3.0:
        return Level.NO_TRAVEL
    if inches_per_hour >= 2.0:
        return Level.SEVERE
    if inches_per_hour >= 1.0:
        return Level.HIGH
    if inches_per_hour >= 0.5:
        return Level.MODERATE
    return Level.LOW


def classify_wind_with_load(mph: float, load_lb: float) -> Level:
    """Wind level after the cargo-weight overrides."""
    level = classify_wind(mph)
    if 45 <= mph < 55 and load_lb > HEAVY_LOAD_NO_TRAVEL_LB:
        return Level.NO_TRAVEL
    if 35 <= mph < 45 and load_lb > HEAVY_LOAD_SEVERE_LB:
        return max(level, Level.SEVERE)
    return level


@dataclass(frozen=True)
class RiskAssessment:
    wind: Level | None
    rain: Level | None
    snow: Level | None
    overall: Level | None  # highest known level; None if nothing was readable
    complete: bool  # False if any of wind, rain, snow was missing or invalid
    reasons: tuple

    @property
    def is_no_travel(self) -> bool:
        return self.overall == Level.NO_TRAVEL


def _clean(value):
    """A usable non-negative float, or None. Rounds away floating-point noise."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return round(number, 6)


def _validate_load(load_lb) -> float:
    try:
        load = float(load_lb)
    except (TypeError, ValueError):
        raise ValueError("load_lb must be a number") from None
    if not math.isfinite(load) or load < 0:
        raise ValueError("load_lb must be a finite, non-negative number")
    return load


def assess(wind_mph, rain_in_hr, snow_in_hr, load_lb) -> RiskAssessment:
    """Classify one checkpoint. The highest known level wins; No Travel is a safety flag."""
    load = _validate_load(load_lb)
    wind = _clean(wind_mph)
    rain = _clean(rain_in_hr)
    snow = _clean(snow_in_hr)
    reasons = []

    wind_level = rain_level = snow_level = None

    if wind is not None:
        base = classify_wind(wind)
        wind_level = classify_wind_with_load(wind, load)
        note = f"Wind {wind:g} mph: {base.label}"
        if wind_level != base:
            note += f", raised to {wind_level.label} by a {load:,.0f} lb load"
        reasons.append(note)
    else:
        reasons.append("Wind unavailable")

    if rain is not None:
        rain_level = classify_rain(rain)
        reasons.append(f"Rain {rain:g} in/hr: {rain_level.label}")
    else:
        reasons.append("Rain unavailable")

    if snow is not None:
        snow_level = classify_snow(snow)
        reasons.append(f"Snow {snow:g} in/hr: {snow_level.label}")
    else:
        reasons.append("Snow unavailable")

    known = [lv for lv in (wind_level, rain_level, snow_level) if lv is not None]
    return RiskAssessment(
        wind=wind_level,
        rain=rain_level,
        snow=snow_level,
        overall=max(known) if known else None,
        complete=len(known) == 3,
        reasons=tuple(reasons),
    )