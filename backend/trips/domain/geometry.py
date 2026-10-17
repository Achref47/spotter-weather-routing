"""Simplify a route polyline for drawing on the map. Pure functions, no I/O.

Only the line sent to the browser is simplified. Checkpoints, ETAs and distances are
always computed from the full-detail geometry that the routing API returned.
Coordinates follow GeoJSON order: [longitude, latitude].
"""
import math

METERS_PER_DEG_LAT = 111_320.0


def _project(coords):
    """Flat (x, y) meters around the route's mean latitude: accurate enough for simplifying."""
    mean_lat = math.radians(sum(lat for _, lat in coords) / len(coords))
    kx = METERS_PER_DEG_LAT * math.cos(mean_lat)
    return [(lon * kx, lat * METERS_PER_DEG_LAT) for lon, lat in coords]


def _distance_to_segment(p, a, b) -> float:
    px, py = p
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def simplify_line(coords, tolerance_m: float, decimals: int = 5):
    """Douglas-Peucker: drop points that lie within tolerance_m of the simplified line.

    The first and last points are always kept, so the line still starts and ends at the
    same places. Coordinates are rounded to `decimals` places (5 is about 1 meter).
    Returns a new list; the input is not modified.
    """
    if tolerance_m < 0:
        raise ValueError("tolerance_m must not be negative")
    n = len(coords)
    keep = [True] * n
    if n > 2:
        points = _project(coords)
        keep = [False] * n
        keep[0] = keep[-1] = True
        stack = [(0, n - 1)]  # explicit stack: routes have 10,000+ points
        while stack:
            first, last = stack.pop()
            farthest, farthest_d = -1, tolerance_m
            for k in range(first + 1, last):
                d = _distance_to_segment(points[k], points[first], points[last])
                if d > farthest_d:
                    farthest, farthest_d = k, d
            if farthest != -1:
                keep[farthest] = True
                stack.append((first, farthest))
                stack.append((farthest, last))
    return [[round(lon, decimals), round(lat, decimals)] for (lon, lat), k in zip(coords, keep) if k]
