"""Choose up to three genuinely different routes from candidate routes.

Pure functions only (no network). Coordinates are GeoJSON order [lon, lat].
"""
import math
from dataclasses import dataclass

from .checkpoints import METERS_PER_MILE, haversine_m

SAMPLE_STEP_M = METERS_PER_MILE  # sample routes about once per mile
NEAR_M = 1500.0  # a point this close to the other route counts as shared road
CELL_DEG = 0.05  # spatial-hash cell size (about 5 km); keeps matching fast


@dataclass(frozen=True)
class Candidate:
    label: str
    source: str  # "alternative" (from the routing API) or "via_waypoint"
    distance_m: float
    duration_s: float
    coords: list  # [[lon, lat], ...]


def resample(coords, step_m):
    """Points (lat, lon) every step_m meters along a polyline, starting at its start."""
    pts = [(coords[0][1], coords[0][0])]
    carry = 0.0  # distance travelled since the last emitted point
    for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:]):
        seg = haversine_m(lat1, lon1, lat2, lon2)
        if seg == 0:
            continue
        pos = step_m - carry  # distance into this segment of the next point
        while pos <= seg:
            t = pos / seg
            pts.append((lat1 + t * (lat2 - lat1), lon1 + t * (lon2 - lon1)))
            pos += step_m
        carry = seg - (pos - step_m)
    return pts


def _cell(lat, lon):
    return (math.floor(lat / CELL_DEG), math.floor(lon / CELL_DEG))


def _index(points):
    grid = {}
    for lat, lon in points:
        grid.setdefault(_cell(lat, lon), []).append((lat, lon))
    return grid


def _near(lat, lon, grid):
    ci, cj = _cell(lat, lon)
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            for plat, plon in grid.get((ci + di, cj + dj), ()):
                if haversine_m(lat, lon, plat, plon) <= NEAR_M:
                    return True
    return False


def overlap_fraction(a_coords, b_coords):
    """Share (0 to 1) of route A that lies within NEAR_M of route B."""
    a_pts = resample(a_coords, SAMPLE_STEP_M)
    grid = _index(resample(b_coords, SAMPLE_STEP_M))
    hits = sum(1 for lat, lon in a_pts if _near(lat, lon, grid))
    return hits / len(a_pts)


def _is_duplicate(a_coords, b_coords, max_overlap):
    return max(
        overlap_fraction(a_coords, b_coords),
        overlap_fraction(b_coords, a_coords),
    ) > max_overlap


def select_routes(candidates, max_routes=3, max_duration_ratio=1.5, max_overlap=0.9):
    """Fastest route first, then the next-fastest routes that are truly different."""
    ordered = sorted(candidates, key=lambda c: c.duration_s)
    if not ordered:
        return []
    fastest = ordered[0]
    chosen = [fastest]
    for cand in ordered[1:]:
        if len(chosen) >= max_routes:
            break
        if cand.duration_s > max_duration_ratio * fastest.duration_s:
            continue
        if any(_is_duplicate(cand.coords, k.coords, max_overlap) for k in chosen):
            continue
        chosen.append(cand)
    return chosen


def via_points(coords, offset_fraction=0.12):
    """Two (lat, lon) points beside the middle of a route: left and right of travel.

    Used to ask the routing API for a route through a different corridor.
    Offset = offset_fraction of the straight-line start-to-end distance.
    """
    if len(coords) < 2:
        return []
    lon0, lat0 = coords[0]
    lon1, lat1 = coords[-1]
    straight_m = haversine_m(lat0, lon0, lat1, lon1)
    if straight_m < 1.0:
        return []
    pts = resample(coords, SAMPLE_STEP_M)
    mid_lat, mid_lon = pts[len(pts) // 2]
    cos_lat = max(math.cos(math.radians(mid_lat)), 0.01)
    dx = (lon1 - lon0) * cos_lat
    dy = lat1 - lat0
    norm = math.hypot(dx, dy)
    ux, uy = dx / norm, dy / norm
    offset_deg = offset_fraction * straight_m / 111_320.0
    return [
        (mid_lat + py * offset_deg, mid_lon + px * offset_deg / cos_lat)
        for px, py in ((-uy, ux), (uy, -ux))
    ]