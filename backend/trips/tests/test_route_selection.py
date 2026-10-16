import pytest

from trips.domain.route_selection import (
    Candidate,
    overlap_fraction,
    resample,
    select_routes,
    via_points,
)


def line(lat, lon_end=1.0):
    return [[0.0, lat], [lon_end, lat]]


def cand(label, lat, duration):
    return Candidate(label, "alternative", 111_000.0, float(duration), line(lat))


def test_resample_one_point_per_mile():
    pts = resample(line(0.0), 1609.344)
    assert len(pts) == 70
    assert pts[0] == (0.0, 0.0)


def test_resample_is_independent_of_segment_splits():
    split = [[i / 10, 0.0] for i in range(11)]
    assert len(resample(split, 1609.344)) == 70


def test_overlap_identical_routes_is_one():
    assert overlap_fraction(line(0.0), line(0.0)) == 1.0


def test_overlap_far_apart_routes_is_zero():
    assert overlap_fraction(line(0.0), line(0.5)) == 0.0


def test_overlap_partial_share():
    detour = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5]]
    assert 0.4 < overlap_fraction(detour, line(0.0)) < 0.65


def test_select_empty_and_single():
    assert select_routes([]) == []
    only = cand("A", 0.0, 1000)
    assert select_routes([only]) == [only]


def test_select_drops_duplicates_and_caps_at_three():
    a = cand("A", 0.0, 1000)
    dup = cand("dup", 0.0, 1010)
    e = cand("E", 1.0, 1100)
    c = cand("C", 0.5, 1200)
    d = cand("D", -0.5, 1300)
    chosen = select_routes([d, c, dup, e, a])
    assert [r.label for r in chosen] == ["A", "E", "C"]


def test_select_excludes_routes_much_slower_than_fastest():
    chosen = select_routes([cand("A", 0.0, 1000), cand("slow", 0.5, 1501)])
    assert [r.label for r in chosen] == ["A"]


def test_select_includes_route_exactly_at_ratio_limit():
    chosen = select_routes([cand("A", 0.0, 1000), cand("edge", 0.5, 1500)])
    assert [r.label for r in chosen] == ["A", "edge"]


def test_via_points_sit_on_both_sides_of_the_route():
    left, right = via_points(line(0.0, lon_end=2.0))
    assert left[0] == pytest.approx(0.24, abs=0.01)
    assert right[0] == pytest.approx(-0.24, abs=0.01)
    assert left[1] == pytest.approx(1.0, abs=0.02)
    assert right[1] == pytest.approx(1.0, abs=0.02)


def test_via_points_empty_when_start_equals_end():
    assert via_points([[1.0, 1.0], [1.0, 1.0]]) == []