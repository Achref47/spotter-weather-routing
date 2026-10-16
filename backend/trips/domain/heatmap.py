"""Corridor sampling and hour-by-hour risk for the forecast heatmap. Pure functions.

Slider meaning: hour N shows the forecast risk at each corridor point at the clock time
departure + N hours. It does not depend on where the truck is at that moment; the
per-checkpoint risk on the route cards is the one that uses each truck's ETA.

Each point carries HEATMAP_HOURS + 1 values: 0 to 4 for Low to No Travel (the Level
numbers) and UNKNOWN (-1) when no weather could be read.
"""
import math
from datetime import timedelta

from .checkpoints import METERS_PER_MILE
from .risk import Level, assess
from .route_selection import resample
from .weather_match import weather_at

HEATMAP_HOURS = 48
UNKNOWN = -1
CELL_DEG = 0.1  # about 7 miles: closer points add nothing at forecast-model resolution
MAX_STEP_MI = 200.0


def _collect(routes_coords, step_mi):
    seen, points = set(), []
    for coords in routes_coords:
        route_points = resample(coords, step_mi * METERS_PER_MILE)
        route_points.append((coords[-1][1], coords[-1][0]))  # always include the endpoint
        for lat, lon in route_points:
            cell = (math.floor(lat / CELL_DEG), math.floor(lon / CELL_DEG))
            if cell not in seen:
                seen.add(cell)
                points.append((lat, lon))
    return points


def sample_corridor(routes_coords, step_mi=25.0, max_points=80):
    """(lat, lon) points along every route, de-duplicated, at most max_points of them.

    If there are too many, the spacing is widened until they fit.
    """
    step = step_mi
    while True:
        points = _collect(routes_coords, step)
        if len(points) <= max_points or step >= MAX_STEP_MI:
            break
        step *= 1.5
    if len(points) > max_points:
        points = points[:: math.ceil(len(points) / max_points)]
    return points


def hourly_levels(series, departure, load_lb, hours=HEATMAP_HOURS):
    """Risk level (0 to 4, or UNKNOWN) at departure + 0..hours hours for one location."""
    levels = []
    for h in range(hours + 1):
        wx = weather_at(series, departure + timedelta(hours=h))
        overall = assess(wx["wind_mph"], wx["rain_in_hr"], wx["snow_in_hr"], load_lb).overall
        levels.append(UNKNOWN if overall is None else int(overall))
    return levels


def build_heatmap(points, series_list, departure, load_lb, hours=HEATMAP_HOURS):
    legend = {str(UNKNOWN): "Unknown"}
    legend.update({str(int(level)): level.label for level in Level})
    return {
        "start_time": departure.isoformat(),
        "hours": hours,
        "legend": legend,
        "points": [
            {
                "lat": round(lat, 3),
                "lon": round(lon, 3),
                "levels": hourly_levels(series, departure, load_lb, hours),
            }
            for (lat, lon), series in zip(points, series_list)
        ],
    }