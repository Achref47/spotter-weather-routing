"""Distance-weighted route statistics and route ranking. Pure functions, no I/O.

Segments
    The stretch between two consecutive checkpoints is one segment. Its level is the
    WORSE of its two endpoint levels (conservative). Segment lengths add up exactly to
    the route length, so the final short section is included and nothing is counted twice.

Risk scale for the average: Low=0, Moderate=1, High=2, Severe=3, No Travel=4.
Each level's miles are exclusive: "Severe miles" does not include No Travel miles.

Unknown data
    A segment with one unknown endpoint uses the known endpoint (a lower bound).
    A segment with two unknown endpoints is "unknown": it is left out of the average and
    reported separately. Unknown is never treated as Low.
"""
import math
from dataclasses import dataclass

from .risk import Level

CRITERIA = ("No Travel miles", "Severe miles", "High miles", "average risk", "travel time")


@dataclass(frozen=True)
class RouteStats:
    total_mi: float
    low_mi: float
    moderate_mi: float
    high_mi: float
    severe_mi: float
    no_travel_mi: float
    unknown_mi: float
    avg_risk: float | None


def compute_stats(miles, levels) -> RouteStats:
    """miles: ascending checkpoint miles. levels: a Level or None for each checkpoint."""
    if len(miles) != len(levels) or len(miles) < 2:
        raise ValueError("need at least two checkpoints, with one level each")
    if any(b < a for a, b in zip(miles, miles[1:])):
        raise ValueError("checkpoint miles must not decrease")

    buckets = {level: 0.0 for level in Level}
    unknown = 0.0
    for i in range(len(miles) - 1):
        length = miles[i + 1] - miles[i]
        known = [lv for lv in (levels[i], levels[i + 1]) if lv is not None]
        if known:
            buckets[max(known)] += length
        else:
            unknown += length

    known_total = sum(buckets.values())
    avg = None
    if known_total > 0:
        avg = sum(int(level) * dist for level, dist in buckets.items()) / known_total

    return RouteStats(
        total_mi=miles[-1] - miles[0],
        low_mi=buckets[Level.LOW],
        moderate_mi=buckets[Level.MODERATE],
        high_mi=buckets[Level.HIGH],
        severe_mi=buckets[Level.SEVERE],
        no_travel_mi=buckets[Level.NO_TRAVEL],
        unknown_mi=unknown,
        avg_risk=avg,
    )


def _round(value, digits):
    return value if math.isinf(value) else round(value, digits)


def ranking_key(stats: RouteStats, duration_s: float) -> tuple:
    """Lexicographic key: No Travel gate, then Severe, High, average risk, travel time.

    Lower is better. Unknown average risk sorts after any known value. Values are rounded
    so floating-point noise cannot decide a comparison.
    """
    avg = float("inf") if stats.avg_risk is None else stats.avg_risk
    return (
        stats.no_travel_mi,
        _round(stats.severe_mi, 3),
        _round(stats.high_mi, 3),
        _round(avg, 4),
        round(duration_s),
    )


def _describe(index: int, entry: dict) -> str:
    s = entry["stats"]
    if index == 1:
        return f"{s.severe_mi:.1f} mi"
    if index == 2:
        return f"{s.high_mi:.1f} mi"
    if index == 3:
        return "n/a" if s.avg_risk is None else f"{s.avg_risk:.2f}"
    return f"{entry['duration_s'] / 3600:.1f} h"


def recommend(entries) -> dict:
    """entries: dicts with id, label, stats (RouteStats), duration_s, optional incomplete.

    Returns route_id (None when there is no safe route), status, explanation, ranking.
    """
    if not entries:
        return {"route_id": None, "status": "no_routes",
                "explanation": "No routes were available.", "ranking": []}

    ordered = sorted(entries, key=lambda e: ranking_key(e["stats"], e["duration_s"]))
    ranking = [e["id"] for e in ordered]
    incomplete = any(e["stats"].unknown_mi > 0 or e.get("incomplete", False) for e in entries)
    note = " Some forecast data was unavailable, so this is based on incomplete data." if incomplete else ""

    safe = [e for e in ordered if e["stats"].no_travel_mi <= 0]
    if not safe:
        least = ordered[0]
        text = (
            "No safe route is available: every route has No Travel conditions at the planned "
            f"time. {least['label']} is least affected ({least['stats'].no_travel_mi:.1f} No "
            "Travel mi). Consider delaying departure."
        )
        return {"route_id": None, "status": "no_safe_route",
                "explanation": text + note, "ranking": ranking}

    best = safe[0]
    if len(entries) == 1:
        why = f"{best['label']} is the only route found."
    elif len(safe) == 1:
        why = f"{best['label']} is the only route without No Travel conditions."
    else:
        second = safe[1]
        k1 = ranking_key(best["stats"], best["duration_s"])
        k2 = ranking_key(second["stats"], second["duration_s"])
        idx = next((i for i in range(1, 5) if k1[i] != k2[i]), None)
        if idx is None:
            why = (f"{best['label']} ties with the other routes on every criterion, "
                   "so the first listed route was chosen.")
        else:
            why = (f"{best['label']} ranks first on {CRITERIA[idx]} "
                   f"({_describe(idx, best)} vs {_describe(idx, second)}).")

    excluded = len(entries) - len(safe)
    if excluded:
        why += f" {excluded} route(s) with No Travel conditions were excluded."

    return {
        "route_id": best["id"],
        "status": "incomplete_data" if incomplete else "recommended",
        "explanation": why + note,
        "ranking": ranking,
    }