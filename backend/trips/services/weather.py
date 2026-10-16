"""Fetch hourly forecasts from Open-Meteo: batched requests, cached results."""
import math
import threading
import time
from datetime import timezone

import requests

from trips.domain.weather_match import HourlySeries
from trips.errors import WeatherError

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARS = "wind_speed_10m,rain,showers,snowfall"
BATCH_SIZE = 50
TIMEOUT_S = 20
CACHE_TTL_S = 1800
CACHE_MAX_ENTRIES = 5000
MAX_FORECAST_DAYS = 16
WIND_UNITS = {"mp/h", "mph"}
PRECIP_UNITS = {"inch", "in"}

_cache = {}  # (lat, lon) -> (stored_at, forecast_days, HourlySeries)
_lock = threading.Lock()


def _now() -> float:
    return time.monotonic()


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def grid_key(lat: float, lon: float) -> tuple:
    """Round to 0.01 degrees (about 1 km): finer than the forecast models resolve."""
    return round(lat, 2), round(lon, 2)


def forecast_days_for(last_time, now) -> int:
    """Forecast days (counted from 00:00 UTC today) needed to cover last_time."""
    now = now.astimezone(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days = math.floor((last_time - start).total_seconds() / 86400) + 1
    return max(1, min(MAX_FORECAST_DAYS, days))


def _build_url(keys, days: int) -> str:
    lats = ",".join(f"{lat:.2f}" for lat, _ in keys)
    lons = ",".join(f"{lon:.2f}" for _, lon in keys)
    return (
        f"{FORECAST_URL}?latitude={lats}&longitude={lons}&hourly={HOURLY_VARS}"
        f"&wind_speed_unit=mph&precipitation_unit=inch&timeformat=unixtime"
        f"&timezone=GMT&forecast_days={days}"
    )


def _num(value):
    return None if value is None else float(value)


def _parse_location(loc) -> HourlySeries:
    try:
        units = loc["hourly_units"]
        hourly = loc["hourly"]
        times = hourly["time"]
        wind = hourly["wind_speed_10m"]
        rain = hourly["rain"]
        showers = hourly["showers"]
        snow = hourly["snowfall"]
        unit_ok = (
            units["wind_speed_10m"] in WIND_UNITS
            and units["rain"] in PRECIP_UNITS
            and units["showers"] in PRECIP_UNITS
            and units["snowfall"] in PRECIP_UNITS
        )
        n = len(times)
        if not (len(wind) == len(rain) == len(showers) == len(snow) == n):
            raise WeatherError("Unexpected response from weather service.")
        times = tuple(int(t) for t in times)
        wind = tuple(_num(v) for v in wind)
        liquid = tuple(
            None if r is None or s is None else float(r) + float(s)
            for r, s in zip(rain, showers)
        )
        snow = tuple(_num(v) for v in snow)
    except (KeyError, TypeError, ValueError, AttributeError):
        raise WeatherError("Unexpected response from weather service.") from None
    if not unit_ok:
        raise WeatherError("The weather service returned unexpected units.")
    return HourlySeries(times=times, wind_mph=wind, liquid_in_hr=liquid, snow_in_hr=snow)


def _fetch_batch(keys, days: int):
    try:
        resp = requests.get(_build_url(keys, days), timeout=TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise WeatherError("The weather service is unavailable.") from exc
    # One location returns an object; several return a list.
    locations = data if isinstance(data, list) else [data]
    if len(locations) != len(keys):
        raise WeatherError("Unexpected response from weather service.")
    return [_parse_location(loc) for loc in locations]


def series_for_points(points, forecast_days: int):
    """Hourly forecast for each (lat, lon), in the same order as points.

    Nearby points share one request slot, results are cached for 30 minutes, and
    uncached locations are fetched in batches of 50.
    """
    keys = [grid_key(lat, lon) for lat, lon in points]
    result = {}
    missing = []
    now = _now()
    with _lock:
        for key in dict.fromkeys(keys):
            entry = _cache.get(key)
            if entry and now - entry[0] < CACHE_TTL_S and entry[1] >= forecast_days:
                result[key] = entry[2]
            else:
                missing.append(key)

    for i in range(0, len(missing), BATCH_SIZE):
        batch = missing[i : i + BATCH_SIZE]
        for key, series in zip(batch, _fetch_batch(batch, forecast_days)):
            result[key] = series
            with _lock:
                if len(_cache) >= CACHE_MAX_ENTRIES:
                    _cache.clear()
                _cache[key] = (_now(), forecast_days, series)

    return [result[k] for k in keys]