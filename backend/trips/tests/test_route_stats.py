import pytest

from trips.domain.risk import Level
from trips.domain.route_stats import RouteStats, compute_stats, recommend

L, M, H, S, N = Level.LOW, Level.MODERATE, Level.HIGH, Level.SEVERE, Level.NO_TRAVEL


def test_all_low():
    s = compute_stats([0, 25, 50], [L, L, L])
    assert s.low_mi == 50 and s.avg_risk == 0.0 and s.total_mi == 50
    assert s.severe_mi == s.high_mi == s.no_travel_mi == s.unknown_mi == 0


def test_segment_takes_the_worse_endpoint():
    s = compute_stats([0, 25, 50], [L, H, L])
    assert s.high_mi == 50 and s.low_mi == 0 and s.avg_risk == 2.0


def test_final_short_segment_is_included():
    s = compute_stats([0, 25, 30], [L, L, S])
    assert s.low_mi == 25 and s.severe_mi == 5
    assert s.avg_risk == pytest.approx(0.5)


def test_no_travel_is_separate_from_severe():
    s = compute_stats([0, 10], [L, N])
    assert s.no_travel_mi == 10 and s.severe_mi == 0 and s.avg_risk == 4.0


def test_two_unknown_endpoints_are_unknown_not_low():
    s = compute_stats([0, 10], [None, None])
    assert s.unknown_mi == 10 and s.low_mi == 0 and s.avg_risk is None


def test_one_unknown_endpoint_uses_the_known_one():
    s = compute_stats([0, 10], [None, M])
    assert s.moderate_mi == 10 and s.unknown_mi == 0


def test_mixed_unknown_segments():
    s = compute_stats([0, 10, 20, 30], [L, None, None, L])
    assert s.low_mi == 20 and s.unknown_mi == 10 and s.avg_risk == 0.0


def test_distance_weighted_average_and_buckets_add_up():
    s = compute_stats([0, 10, 25, 40, 41.5], [L, M, H, None, S])
    assert s.moderate_mi == pytest.approx(10)
    assert s.high_mi == pytest.approx(30)
    assert s.severe_mi == pytest.approx(1.5)
    assert s.avg_risk == pytest.approx(74.5 / 41.5)
    total = s.low_mi + s.moderate_mi + s.high_mi + s.severe_mi + s.no_travel_mi + s.unknown_mi
    assert total == pytest.approx(s.total_mi)


@pytest.mark.parametrize(
    "miles, levels",
    [([0], [L]), ([0, 10], [L]), ([0, 10, 5], [L, L, L])],
)
def test_invalid_inputs_raise(miles, levels):
    with pytest.raises(ValueError):
        compute_stats(miles, levels)


def stats(sev=0.0, high=0.0, avg=0.0, nt=0.0, unknown=0.0):
    return RouteStats(
        total_mi=100.0, low_mi=0.0, moderate_mi=0.0, high_mi=high, severe_mi=sev,
        no_travel_mi=nt, unknown_mi=unknown, avg_risk=avg,
    )


def entry(id_, duration=3600, incomplete=False, **kw):
    return {"id": id_, "label": id_, "stats": stats(**kw), "duration_s": duration,
            "incomplete": incomplete}


def test_severe_miles_decide_before_everything_else():
    a = entry("A", sev=0, high=100, avg=2, duration=9000)
    b = entry("B", sev=5, high=0, avg=0.1, duration=100)
    result = recommend([b, a])
    assert result["route_id"] == "A" and result["ranking"] == ["A", "B"]


def test_high_miles_decide_when_severe_ties():
    result = recommend([entry("A", high=10, avg=0.1, duration=100),
                        entry("B", high=5, avg=3, duration=9000)])
    assert result["route_id"] == "B"


def test_average_risk_decides_next():
    result = recommend([entry("A", avg=1.0, duration=100), entry("B", avg=0.5, duration=9000)])
    assert result["route_id"] == "B"


def test_travel_time_decides_last():
    result = recommend([entry("A", duration=4000), entry("B", duration=3000)])
    assert result["route_id"] == "B"


def test_full_tie_keeps_input_order():
    result = recommend([entry("A"), entry("B")])
    assert result["route_id"] == "A"
    assert "ties" in result["explanation"]


def test_floating_point_noise_is_treated_as_a_tie():
    result = recommend([entry("A", sev=5.0000001, high=10), entry("B", sev=5.0, high=5)])
    assert result["route_id"] == "B"


def test_no_travel_route_is_excluded_when_a_safe_one_exists():
    result = recommend([entry("A", nt=20, sev=0), entry("B", sev=50)])
    assert result["route_id"] == "B" and result["status"] == "recommended"
    assert "excluded" in result["explanation"]


def test_all_routes_no_travel_means_no_safe_route():
    result = recommend([entry("A", nt=30), entry("B", nt=10)])
    assert result["route_id"] is None and result["status"] == "no_safe_route"
    assert result["ranking"] == ["B", "A"]
    assert "No safe route" in result["explanation"]


def test_unknown_miles_flag_the_recommendation():
    result = recommend([entry("A", unknown=10), entry("B", duration=9999)])
    assert result["status"] == "incomplete_data"
    assert "incomplete data" in result["explanation"]


def test_incomplete_flag_alone_marks_the_recommendation():
    assert recommend([entry("A", incomplete=True)])["status"] == "incomplete_data"


def test_unknown_average_ranks_after_a_known_one():
    result = recommend([entry("A", avg=None), entry("B", avg=3.0)])
    assert result["route_id"] == "B"


def test_no_entries():
    assert recommend([])["status"] == "no_routes"


def test_single_route_explanation():
    assert "only route found" in recommend([entry("A")])["explanation"]


def test_explanation_names_the_deciding_criterion():
    result = recommend([entry("A", sev=0), entry("B", sev=12.5)])
    assert "Severe miles" in result["explanation"] and "12.5" in result["explanation"]

# --- structured comparison (the "why this route" trail) ------------------------------------------

import itertools  # noqa: E402

KEYS = ["severe_miles", "high_miles", "average_risk", "travel_time"]


def outcomes(result):
    return [step["outcome"] for step in result["comparison"]["trail"]]


def test_trail_lists_the_four_criteria_in_the_required_order():
    trail = recommend([entry("A"), entry("B")])["comparison"]["trail"]
    assert [step["key"] for step in trail] == KEYS
    assert [step["label"] for step in trail] == [
        "Fewest Severe miles", "Fewest High miles", "Lowest average risk", "Shortest travel time",
    ]


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (dict(sev=0), dict(sev=5), ["decisive", "not_needed", "not_needed", "not_needed"]),
        (dict(high=5), dict(high=10), ["tied", "decisive", "not_needed", "not_needed"]),
        (dict(avg=0.5), dict(avg=1.0), ["tied", "tied", "decisive", "not_needed"]),
        (dict(duration=3000), dict(duration=4000), ["tied", "tied", "tied", "decisive"]),
        ({}, {}, ["tied", "tied", "tied", "tied"]),
    ],
)
def test_trail_marks_each_step_tied_decisive_or_not_needed(a, b, expected):
    assert outcomes(recommend([entry("A", **a), entry("B", **b)])) == expected


def test_trail_values_are_best_first_then_runner_up():
    result = recommend([entry("A", sev=12.5), entry("B", sev=0)])
    step = result["comparison"]["trail"][0]
    assert result["route_id"] == "B" and result["comparison"]["runner_up_id"] == "A"
    assert (step["best"], step["runner_up"]) == ("0.0 mi", "12.5 mi")


def test_a_decisive_step_never_reads_as_identical_values():
    result = recommend([entry("A", sev=5.01), entry("B", sev=5.0)])
    step = result["comparison"]["trail"][0]
    assert (step["best"], step["runner_up"]) == ("5.00 mi", "5.01 mi")
    assert "5.00 mi vs 5.01 mi" in result["explanation"]


def test_a_decisive_time_step_adds_precision_until_the_values_differ():
    result = recommend([entry("A", duration=3610), entry("B", duration=3600)])
    step = result["comparison"]["trail"][3]
    assert (step["best"], step["runner_up"]) == ("1 h 00 min 00 s", "1 h 00 min 10 s")
    wide = recommend([entry("A", duration=43_200), entry("B", duration=42_600)])["comparison"]["trail"][3]
    assert (wide["best"], wide["runner_up"]) == ("11.8 h", "12.0 h")


def test_unknown_average_risk_is_shown_as_n_a():
    result = recommend([entry("A", avg=None), entry("B", avg=3.0)])
    step = result["comparison"]["trail"][2]
    assert (step["best"], step["runner_up"]) == ("3.00", "n/a")


def test_trail_agrees_with_an_independent_ranking_for_every_combination():
    """Oracle: plain tuple comparison of (severe, high, average, time). The backend winner and
    its decisive criterion must match for all 256 pairs of routes."""
    values = list(itertools.product((0, 5), (0, 5), (0.5, 1.0), (3000, 4000)))
    for (sa, ha, ra, ta), (sb, hb, rb, tb) in itertools.product(values, values):
        a = entry("A", sev=sa, high=ha, avg=ra, duration=ta)
        b = entry("B", sev=sb, high=hb, avg=rb, duration=tb)
        result = recommend([a, b])
        left, right = (sa, ha, ra, ta), (sb, hb, rb, tb)
        expected_best = "A" if left <= right else "B"  # a full tie keeps the first listed route
        assert result["route_id"] == expected_best, (left, right)
        first_difference = next((i for i in range(4) if left[i] != right[i]), None)
        marks = outcomes(result)
        if first_difference is None:
            assert marks == ["tied"] * 4
        else:
            assert marks.index("decisive") == first_difference, (left, right)
            assert marks[:first_difference] == ["tied"] * first_difference
            assert set(marks[first_difference + 1:]) <= {"not_needed"}
            label_word = {"severe_miles": "Severe miles", "high_miles": "High miles",
                          "average_risk": "average risk", "travel_time": "travel time"}[KEYS[first_difference]]
            assert f"ranks first on {label_word}" in result["explanation"], (left, right)


def test_the_safety_gate_comes_first_and_lists_the_excluded_routes_worst_first():
    result = recommend([entry("A", nt=20, sev=0, duration=100), entry("B", sev=50, duration=9000),
                        entry("C", nt=45)])
    cmp = result["comparison"]
    assert result["route_id"] == "B"  # more Severe miles, but the only route without No Travel
    assert cmp["excluded"] == [
        {"id": "C", "label": "C", "no_travel_mi": 45.0},
        {"id": "A", "label": "A", "no_travel_mi": 20.0},
    ]
    assert cmp["trail"] == [] and cmp["runner_up_id"] is None  # no second safe route to compare


def test_the_trail_compares_only_routes_that_passed_the_gate():
    result = recommend([entry("A", nt=10, sev=0), entry("B", sev=5), entry("C", sev=9)])
    cmp = result["comparison"]
    assert result["route_id"] == "B" and cmp["runner_up_id"] == "C"
    assert [e["id"] for e in cmp["excluded"]] == ["A"]
    assert outcomes(result)[0] == "decisive"


def test_no_safe_route_lists_every_route_as_excluded_and_has_no_trail():
    result = recommend([entry("A", nt=30), entry("B", nt=10)])
    cmp = result["comparison"]
    assert result["route_id"] is None
    assert [e["id"] for e in cmp["excluded"]] == ["A", "B"]
    assert cmp["trail"] == [] and cmp["runner_up_id"] is None


def test_single_route_and_no_routes():
    single = recommend([entry("A")])["comparison"]
    assert single == {"runner_up_id": None, "runner_up_label": None, "trail": [], "excluded": []}
    assert recommend([])["comparison"] is None
