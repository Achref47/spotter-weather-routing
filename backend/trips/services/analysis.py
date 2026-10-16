"""Orchestrate one trip analysis: geocode, route, checkpoints, weather, risk, ranking."""
from datetime import datetime, timedelta, timezone

from trips.domain.checkpoints import METERS_PER_MILE, generate_checkpoints
from trips.domain.risk import assess
from trips.domain.route_stats import compute_stats, recommend
from trips.domain.weather_match import weather_at
from trips.services.geocoding import geocode
from trips.services.routing import get_route_options
from trips.services.weather import forecast_days_for, series_for_points


def _round(value, digits):
    return None if value is None else round(value, digits)


def _name(level):
    return None if level is None else level.label


def _risk_payload(a):
    return {
        "wind": _name(a.wind),
        "rain": _name(a.rain),
        "snow": _name(a.snow),
        "overall": _name(a.overall),
        "overall_level": None if a.overall is None else int(a.overall),
        "complete": a.complete,
        "reasons": list(a.reasons),
    }


def analyze_trip(data: dict) -> dict:
    origin = geocode(data["origin"])
    destination = geocode(data["destination"])
    options = get_route_options(origin, destination)
    departure = data["departure_time"]  # timezone-aware, UTC
    load_lb = data["load_weight_lb"]
    interval = data["checkpoint_interval_mi"]

    planned = []
    for cand in options:
        cps = generate_checkpoints(cand.coords, cand.distance_m, cand.duration_s, departure, interval)
        planned.append((cand, cps))

    # One batched weather lookup for every checkpoint on every route.
    points = [(c.lat, c.lon) for _, cps in planned for c in cps]
    last_eta = max(c.eta for _, cps in planned for c in cps)
    days = forecast_days_for(last_eta + timedelta(hours=1), datetime.now(timezone.utc))
    series_iter = iter(series_for_points(points, days))

    routes, entries = [], []
    for i, (cand, cps) in enumerate(planned, start=1):
        route_id = f"route-{i}"
        assessments, checkpoint_payloads = [], []
        for c in cps:
            wx = weather_at(next(series_iter), c.eta)
            a = assess(wx["wind_mph"], wx["rain_in_hr"], wx["snow_in_hr"], load_lb)
            assessments.append(a)
            checkpoint_payloads.append(
                {
                    "mile": round(c.mile, 2),
                    "lat": round(c.lat, 5),
                    "lon": round(c.lon, 5),
                    "eta": c.eta.isoformat(),
                    "weather": {
                        "wind_mph": _round(wx["wind_mph"], 1),
                        "rain_in_hr": _round(wx["rain_in_hr"], 3),
                        "snow_in_hr": _round(wx["snow_in_hr"], 3),
                    },
                    "risk": _risk_payload(a),
                }
            )

        stats = compute_stats([c.mile for c in cps], [a.overall for a in assessments])
        incomplete = sum(1 for a in assessments if not a.complete)
        entries.append(
            {
                "id": route_id,
                "label": cand.label,
                "stats": stats,
                "duration_s": cand.duration_s,
                "incomplete": incomplete > 0,
            }
        )
        routes.append(
            {
                "id": route_id,
                "label": cand.label,
                "source": cand.source,
                "distance_mi": round(cand.distance_m / METERS_PER_MILE, 1),
                "duration_s": round(cand.duration_s),
                "arrival_time": (departure + timedelta(seconds=cand.duration_s)).isoformat(),
                "geometry": {"type": "LineString", "coordinates": cand.coords},
                "checkpoints": checkpoint_payloads,
                "summary": {
                    "low_mi": _round(stats.low_mi, 1),
                    "moderate_mi": _round(stats.moderate_mi, 1),
                    "high_mi": _round(stats.high_mi, 1),
                    "severe_mi": _round(stats.severe_mi, 1),
                    "no_travel_mi": _round(stats.no_travel_mi, 1),
                    "unknown_mi": _round(stats.unknown_mi, 1),
                    "avg_risk": _round(stats.avg_risk, 2),
                    "incomplete_checkpoints": incomplete,
                },
            }
        )

    rec = recommend(entries)
    for route in routes:
        route["rank"] = rec["ranking"].index(route["id"]) + 1

    warnings = []
    if len(routes) < 3:
        warnings.append(f"Only {len(routes)} distinct route(s) could be found for this trip.")
    if any(e["incomplete"] for e in entries):
        warnings.append("Weather data was unavailable at some checkpoints.")

    return {
        "origin": origin,
        "destination": destination,
        "departure_time": departure.isoformat(),
        "load_weight_lb": load_lb,
        "checkpoint_interval_mi": interval,
        "routes": routes,
        "recommendation": {
            "route_id": rec["route_id"],
            "status": rec["status"],
            "explanation": rec["explanation"],
        },
        "warnings": warnings,
    }