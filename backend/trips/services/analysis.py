"""Orchestrate one trip analysis: geocode, route, place checkpoints."""
from datetime import timedelta

from trips.domain.checkpoints import METERS_PER_MILE, generate_checkpoints
from trips.services.geocoding import geocode
from trips.services.routing import get_route_options


def analyze_trip(data: dict) -> dict:
    origin = geocode(data["origin"])
    destination = geocode(data["destination"])
    options = get_route_options(origin, destination)
    departure = data["departure_time"]  # timezone-aware, UTC

    routes = []
    for i, cand in enumerate(options, start=1):
        checkpoints = generate_checkpoints(
            cand.coords,
            cand.distance_m,
            cand.duration_s,
            departure,
            data["checkpoint_interval_mi"],
        )
        routes.append(
            {
                "id": f"route-{i}",
                "label": cand.label,
                "source": cand.source,
                "distance_mi": round(cand.distance_m / METERS_PER_MILE, 1),
                "duration_s": round(cand.duration_s),
                "arrival_time": (departure + timedelta(seconds=cand.duration_s)).isoformat(),
                "geometry": {"type": "LineString", "coordinates": cand.coords},
                "checkpoints": [
                    {
                        "mile": round(c.mile, 2),
                        "lat": round(c.lat, 5),
                        "lon": round(c.lon, 5),
                        "eta": c.eta.isoformat(),
                    }
                    for c in checkpoints
                ],
            }
        )

    warnings = []
    if len(routes) < 3:
        warnings.append(
            f"Only {len(routes)} distinct route(s) could be found for this trip."
        )

    return {
        "origin": origin,
        "destination": destination,
        "departure_time": departure.isoformat(),
        "load_weight_lb": data["load_weight_lb"],
        "checkpoint_interval_mi": data["checkpoint_interval_mi"],
        "routes": routes,
        "warnings": warnings,
    }