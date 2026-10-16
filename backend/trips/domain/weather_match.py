"""Match a checkpoint's ETA to forecast values. Pure functions, no I/O.

Open-Meteo conventions (timestamps are unix seconds, UTC):
  - wind_speed_10m is an instantaneous value at the timestamp.
  - rain, showers and snowfall are sums over the PRECEDING hour.
So wind uses the nearest hourly timestamp to the ETA, while precipitation uses the
first timestamp at or after the ETA (the hour that contains the ETA).
"""
import math
from dataclasses import dataclass, field
from datetime import datetime

HOUR_S = 3600


@dataclass(frozen=True)
class HourlySeries:
    times: tuple  # unix seconds, UTC
    wind_mph: tuple  # None where unavailable
    liquid_in_hr: tuple  # rain + showers, inches per hour
    snow_in_hr: tuple  # inches per hour
    _index: dict = field(init=False, repr=False, compare=False, default_factory=dict)

    def __post_init__(self):
        n = len(self.times)
        if not (len(self.wind_mph) == len(self.liquid_in_hr) == len(self.snow_in_hr) == n):
            raise ValueError("series arrays must all have the same length")
        self._index.update({t: i for i, t in enumerate(self.times)})

    def value(self, name: str, timestamp: int):
        i = self._index.get(timestamp)
        return None if i is None else getattr(self, name)[i]


def nearest_hour(ts: float) -> int:
    return math.floor(ts / HOUR_S + 0.5) * HOUR_S


def hour_containing(ts: float) -> int:
    """First hourly timestamp at or after ts (the hour that ends there contains ts)."""
    return math.ceil(ts / HOUR_S) * HOUR_S


def weather_at(series: HourlySeries, eta: datetime) -> dict:
    """Forecast values for an ETA. Any unavailable value is None, never 0."""
    if eta.tzinfo is None or eta.utcoffset() is None:
        raise ValueError("eta must be timezone-aware")
    ts = eta.timestamp()
    precip_ts = hour_containing(ts)
    return {
        "wind_mph": series.value("wind_mph", nearest_hour(ts)),
        "rain_in_hr": series.value("liquid_in_hr", precip_ts),
        "snow_in_hr": series.value("snow_in_hr", precip_ts),
    }