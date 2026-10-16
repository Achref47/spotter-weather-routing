"""Fetch driving routes from Mapbox and choose up to three distinct ones."""
import os
from dataclasses import replace

import requests

from trips.domain.route_selection import Candidate, select_routes, via_points
from trips.errors import RoutingError

MAPBOX_URL = "https://api.mapbox.com/directions/v5/mapbox/driving"
TIMEOUT_S = 20
MAX_ROUTES = 3


def _token() -> str:
    token = os.environ.get("MAPBOX_TOKEN", "").strip()
    if not token:
        raise RoutingError("Routing is not configured (missing MAPBOX_TOKEN).")
    return token


def fetch_routes(points, alternatives):
    """points: [(lat, lon), ...]. Returns a list of dicts: distance_m, duration_s, coords."""
    token = _token()
    coord_str = ";".join(f"{lon},{lat}" for lat, lon in points)
    params = {
        "alternatives": "true" if alternatives else "false",
        "geometries": "geojson",
        "overview": "full",
        "access_token": token,
    }
    try:
        resp = requests.get(f"{MAPBOX_URL}/{coord_str}", params=params, timeout=TIMEOUT_S)
    except requests.RequestException:
        # The original exception contains the request URL (and token): do not chain it.
        raise RoutingError("The routing service is unavailable.") from None

    try:
        data = resp.json()
    except ValueError:
        data = {}
    code = data.get("code") if isinstance(data, dict) else None

    if resp.status_code in (401, 403):
        raise RoutingError("The routing service rejected the API credentials.")
    if resp.status_code == 429:
        raise RoutingError("The routing service rate limit was reached. Try again shortly.")
    if code in ("NoRoute", "NoSegment"):
        raise RoutingError("No drivable route was found between these places.")
    if resp.status_code >= 400 or code != "Ok":
        raise RoutingError("The routing service returned an error.")

    routes = []
    for r in data.get("routes", []):
        try:
            coords = r["geometry"]["coordinates"]
            distance = float(r["distance"])
            duration = float(r["duration"])
        except (KeyError, TypeError, ValueError):
            continue
        if len(coords) >= 2 and distance > 0:
            routes.append({"distance_m": distance, "duration_s": duration, "coords": coords})
    if not routes:
        raise RoutingError("No drivable route was found between these places.")
    return routes


def _to_candidates(routes, source):
    return [Candidate("", source, r["distance_m"], r["duration_s"], r["coords"]) for r in routes]


def _label(chosen):
    counts = {}
    labelled = []
    for i, c in enumerate(chosen):
        if i == 0:
            name = "Fastest route"
        elif c.source == "via_waypoint":
            name = "Alternate corridor"
        else:
            name = "Alternative route"
        counts[name] = counts.get(name, 0) + 1
        if counts[name] > 1:
            name = f"{name} {counts[name]}"
        labelled.append(replace(c, label=name))
    return labelled


def get_route_options(origin, destination):
    """origin/destination: {"lat", "lon"}. Returns up to three labelled Candidates.

    Step 1: ask Mapbox for alternatives. Step 2, only if fewer than three distinct
    routes came back: ask for routes through via points beside the fastest route.
    Stops as soon as there are three. Never duplicates or invents a route.
    """
    start = (origin["lat"], origin["lon"])
    end = (destination["lat"], destination["lon"])

    candidates = _to_candidates(fetch_routes([start, end], alternatives=True), "alternative")
    chosen = select_routes(candidates, MAX_ROUTES)

    if len(chosen) < MAX_ROUTES:
        for via in via_points(chosen[0].coords):
            try:
                extra = fetch_routes([start, via, end], alternatives=False)
            except RoutingError:
                continue  # the fallback is best-effort; keep what we already have
            candidates += _to_candidates(extra, "via_waypoint")
            chosen = select_routes(candidates, MAX_ROUTES)
            if len(chosen) >= MAX_ROUTES:
                break

    return _label(chosen)