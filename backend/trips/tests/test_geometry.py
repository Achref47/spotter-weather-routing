import math

import pytest

from trips.domain.geometry import _distance_to_segment, _project, simplify_line


def test_collinear_points_collapse_to_the_endpoints():
    line = [[i / 100, 0.0] for i in range(101)]
    assert simplify_line(line, 10) == [[0.0, 0.0], [1.0, 0.0]]


def test_a_corner_beyond_the_tolerance_is_kept():
    line = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5]]  # a right angle, about 55 km per leg
    assert simplify_line(line, 10) == line


def test_a_wobble_within_the_tolerance_is_dropped():
    # 0.00005 degrees of latitude is about 5.6 m, below the 10 m tolerance.
    line = [[0.0, 0.0], [0.5, 0.00005], [1.0, 0.0]]
    assert simplify_line(line, 10) == [[0.0, 0.0], [1.0, 0.0]]


def test_the_same_wobble_is_kept_with_a_tighter_tolerance():
    line = [[0.0, 0.0], [0.5, 0.00005], [1.0, 0.0]]
    assert len(simplify_line(line, 2)) == 3


def test_first_and_last_points_are_always_kept():
    line = [[-95.367863, 29.758731], [-95.3677, 29.7586], [-84.38798, 33.749]]
    out = simplify_line(line, 1_000_000)
    assert out == [[-95.36786, 29.75873], [-84.38798, 33.749]]


def test_coordinates_are_rounded():
    out = simplify_line([[0.123456789, 1.987654321], [2.0, 3.0]], 10)
    assert out[0] == [0.12346, 1.98765]


def test_short_lines_are_returned_rounded_and_unchanged_in_length():
    assert simplify_line([[1.0, 2.0]], 10) == [[1.0, 2.0]]
    assert simplify_line([[1.0, 2.0], [3.0, 4.0]], 10) == [[1.0, 2.0], [3.0, 4.0]]


def test_input_is_not_modified():
    line = [[0.0, 0.0], [0.5, 0.00005], [1.0, 0.0]]
    before = [point[:] for point in line]
    simplify_line(line, 10)
    assert line == before


def test_zero_tolerance_keeps_every_point_that_is_off_the_line():
    line = [[0.0, 0.0], [0.5, 0.0001], [1.0, 0.0]]
    assert len(simplify_line(line, 0)) == 3


def test_negative_tolerance_is_rejected():
    with pytest.raises(ValueError):
        simplify_line([[0.0, 0.0], [1.0, 1.0], [2.0, 0.0]], -1)


def test_every_original_point_stays_within_the_tolerance_of_the_result():
    tolerance = 25.0
    line = [[i * 0.002, 0.01 * math.sin(i * 0.05)] for i in range(500)]  # a long smooth curve
    out = simplify_line(line, tolerance, decimals=8)  # fine rounding so only the tolerance matters
    assert 2 < len(out) < len(line)
    projected = _project(line + out)
    original, simple = projected[: len(line)], projected[len(line):]
    for p in original:
        nearest = min(_distance_to_segment(p, a, b) for a, b in zip(simple, simple[1:]))
        assert nearest <= tolerance + 0.5


def test_a_long_noisy_route_is_simplified_and_keeps_its_ends():
    line = [[i * 0.0001, 0.00002 * ((i * 7919) % 13)] for i in range(3_000)]
    out = simplify_line(line, 10)
    assert out[0] == [0.0, 0.0] and out[-1][0] == round(2999 * 0.0001, 5)
    assert len(out) < len(line)
