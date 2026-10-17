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
# The four ranking criteria after the No Travel gate, in the required order (ranking_key[1:5]).
CRITERIA_KEYS = ("severe_miles", "high_miles", "average_risk", "travel_time")
CRITERIA_LABELS = ("Fewest Severe miles", "Fewest High miles", "Lowest average risk", "Shortest travel time")


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


def _hours(seconds: float) -> str:
    return f"{seconds / 3600:.1f} h"


def _clock(seconds: float, with_seconds: bool = False) -> str:
    whole = round(seconds)
    h, rest = divmod(whole, 3600)
    m, sec = divmod(rest, 60)
    return f"{h} h {m:02d} min {sec:02d} s" if with_seconds else f"{h} h {m:02d} min"


def _pair_text(index: int, a: dict, b: dict) -> tuple:
    """Display text for one criterion of two routes. Adds precision until two values that rank
    differently no longer look identical (so a decisive step never reads "0.0 mi vs 0.0 mi")."""
    sa, sb = a["stats"], b["stats"]
    if index in (1, 2):
        va, vb = (sa.severe_mi, sb.severe_mi) if index == 1 else (sa.high_mi, sb.high_mi)
        for digits in (1, 2, 3):
            ta, tb = f"{va:.{digits}f} mi", f"{vb:.{digits}f} mi"
            if ta != tb or va == vb:
                break
        return ta, tb
    if index == 3:
        if sa.avg_risk is None or sb.avg_risk is None:
            return ("n/a" if sa.avg_risk is None else f"{sa.avg_risk:.2f}",
                    "n/a" if sb.avg_risk is None else f"{sb.avg_risk:.2f}")
        for digits in (2, 3, 4):
            ta, tb = f"{sa.avg_risk:.{digits}f}", f"{sb.avg_risk:.{digits}f}"
            if ta != tb or sa.avg_risk == sb.avg_risk:
                break
        return ta, tb
    da, db = a["duration_s"], b["duration_s"]
    ta, tb = _hours(da), _hours(db)
    if ta == tb and round(da) != round(db):
        ta, tb = _clock(da), _clock(db)
    if ta == tb and round(da) != round(db):
        ta, tb = _clock(da, True), _clock(db, True)
    return ta, tb


def _excluded(entries) -> list:
    """Routes the No Travel safety gate removes from the running, worst first."""
    hit = [e for e in entries if e["stats"].no_travel_mi > 0]
    hit.sort(key=lambda e: -e["stats"].no_travel_mi)
    return [{"id": e["id"], "label": e["label"], "no_travel_mi": round(e["stats"].no_travel_mi, 1)}
            for e in hit]


def _trail(best: dict, second: dict, decisive) -> list:
    """The four criteria in order, for best vs runner-up: tied, decisive, or not needed."""
    steps = []
    for i in range(1, 5):
        best_text, second_text = _pair_text(i, best, second)
        if decisive is None or i < decisive:
            outcome = "tied"
        elif i == decisive:
            outcome = "decisive"
        else:
            outcome = "not_needed"
        steps.append({"key": CRITERIA_KEYS[i - 1], "label": CRITERIA_LABELS[i - 1],
                      "best": best_text, "runner_up": second_text, "outcome": outcome})
    return steps


def recommend(entries) -> dict:
    """entries: dicts with id, label, stats (RouteStats), duration_s, optional incomplete.

    Returns route_id (None when there is no safe route), status, explanation, ranking, and a
    structured comparison: the routes the safety gate excluded, and for the best versus the
    runner-up route a trail through the four ranking criteria in order.
    """
    if not entries:
        return {"route_id": None, "status": "no_routes",
                "explanation": "No routes were available.", "ranking": [], "comparison": None}

    ordered = sorted(entries, key=lambda e: ranking_key(e["stats"], e["duration_s"]))
    ranking = [e["id"] for e in ordered]
    incomplete = any(e["stats"].unknown_mi > 0 or e.get("incomplete", False) for e in entries)
    note = " Some forecast data was unavailable, so this is based on incomplete data." if incomplete else ""
    excluded = _excluded(entries)

    safe = [e for e in ordered if e["stats"].no_travel_mi <= 0]
    if not safe:
        least = ordered[0]
        text = (
            "No safe route is available: every route has No Travel conditions at the planned "
            f"time. {least['label']} is least affected ({least['stats'].no_travel_mi:.1f} No "
            "Travel mi). Consider delaying departure."
        )
        return {"route_id": None, "status": "no_safe_route", "explanation": text + note,
                "ranking": ranking,
                "comparison": {"runner_up_id": None, "runner_up_label": None, "trail": [],
                               "excluded": excluded}}

    best = safe[0]
    second = None
    trail = []
    if len(entries) == 1:
        why = f"{best['label']} is the only route found."
    elif len(safe) == 1:
        why = f"{best['label']} is the only route without No Travel conditions."
    else:
        second = safe[1]
        k1 = ranking_key(best["stats"], best["duration_s"])
        k2 = ranking_key(second["stats"], second["duration_s"])
        idx = next((i for i in range(1, 5) if k1[i] != k2[i]), None)
        trail = _trail(best, second, idx)
        if idx is None:
            why = (f"{best['label']} ties with the other routes on every criterion, "
                   "so the first listed route was chosen.")
        else:
            a, b = _pair_text(idx, best, second)
            why = f"{best['label']} ranks first on {CRITERIA[idx]} ({a} vs {b})."

    if excluded:
        why += f" {len(excluded)} route(s) with No Travel conditions were excluded."

    return {
        "route_id": best["id"],
        "status": "incomplete_data" if incomplete else "recommended",
        "explanation": why + note,
        "ranking": ranking,
        "comparison": {
            "runner_up_id": second["id"] if second else None,
            "runner_up_label": second["label"] if second else None,
            "trail": trail,
            "excluded": excluded,
        },
    }
