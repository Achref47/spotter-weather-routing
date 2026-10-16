"""Place weather checkpoints along a route and estimate arrival times.

Pure functions only: no network calls, so everything here is unit-testable.
Coordinates follow GeoJSON order: [longitude, latitude].
"""
import math
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta

METERS_PER_MILE = 1609.344
EARTH_RADIUS_M = 6371008.8
ALLOWED_INTERVALS_MI = (10, 25, 50)


@dataclass(frozen=True)
class Checkpoint:
    mile: float
    lat: float
    lon: float
    eta: datetime


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _point_at(coords, cum, g):
    """Return (lat, lon) at distance g meters along the polyline."""
    if g <= 0:
        return coords[0][1], coords[0][0]
    if g >= cum[-1]:
        return coords[-1][1], coords[-1][0]
    i = bisect_right(cum, g) - 1
    seg = cum[i + 1] - cum[i]
    t = 0.0 if seg == 0 else (g - cum[i]) / seg
    lon = coords[i][0] + t * (coords[i + 1][0] - coords[i][0])
    lat = coords[i][1] + t * (coords[i + 1][1] - coords[i][1])
    return lat, lon


def generate_checkpoints(coords, distance_m, duration_s, departure, interval_mi):
    """Checkpoints at mile 0, every interval_mi, and the route endpoint.

    The polyline length rarely matches the API's reported distance exactly,
    so positions are scaled so the last checkpoint sits at the reported
    total distance. ETA = departure + duration * (mile / total miles).
    """
    if interval_mi <= 0:
        raise ValueError("interval_mi must be positive")
    if len(coords) < 2:
        raise ValueError("route needs at least two coordinates")
    if distance_m <= 0 or duration_s < 0:
        raise ValueError("distance must be positive and duration non-negative")

    cum = [0.0]
    for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:]):
        cum.append(cum[-1] + haversine_m(lat1, lon1, lat2, lon2))
    if cum[-1] == 0:
        raise ValueError("route geometry has zero length")

    scale = distance_m / cum[-1]
    total_mi = distance_m / METERS_PER_MILE

    miles = []
    k = 0
    while k * interval_mi < total_mi - 1e-6:
        miles.append(k * interval_mi)
        k += 1
    miles.append(total_mi)  # always include the endpoint exactly once

    checkpoints = []
    for m in miles:
        lat, lon = _point_at(coords, cum, m * METERS_PER_MILE / scale)
        eta = departure + timedelta(seconds=duration_s * m / total_mi)
        checkpoints.append(Checkpoint(mile=m, lat=lat, lon=lon, eta=eta))
    return checkpoints