from datetime import datetime, timedelta, timezone

import pytest

from trips.domain.checkpoints import (
    METERS_PER_MILE,
    generate_checkpoints,
    haversine_m,
)

DEPART = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
LINE = [[0.0, 0.0], [1.0, 0.0]]  # about 69.09 miles along the equator
LINE_M = haversine_m(0, 0, 0, 1)


def test_first_checkpoint_is_start_and_last_is_endpoint():
    cps = generate_checkpoints(LINE, LINE_M, 3600, DEPART, 25)
    assert cps[0].mile == 0
    assert cps[0].eta == DEPART
    assert cps[-1].mile == pytest.approx(LINE_M / METERS_PER_MILE)
    assert cps[-1].eta == DEPART + timedelta(hours=1)


def test_interval_spacing_and_count():
    cps = generate_checkpoints(LINE, LINE_M, 3600, DEPART, 25)
    assert [round(c.mile, 2) for c in cps] == [0, 25, 50, 69.09]


def test_exact_multiple_does_not_duplicate_endpoint():
    cps = generate_checkpoints(LINE, 100 * METERS_PER_MILE, 7200, DEPART, 25)
    assert [c.mile for c in cps] == [0, 25, 50, 75, 100]


def test_positions_scale_to_reported_distance():
    cps = generate_checkpoints(LINE, 100 * METERS_PER_MILE, 7200, DEPART, 25)
    assert cps[2].lon == pytest.approx(0.5, abs=1e-6)  # mile 50 of 100
    assert cps[2].lat == pytest.approx(0.0, abs=1e-9)


def test_etas_never_decrease():
    cps = generate_checkpoints(LINE, LINE_M, 5400, DEPART, 10)
    etas = [c.eta for c in cps]
    assert etas == sorted(etas)


def test_short_route_gets_start_and_end_only():
    cps = generate_checkpoints(LINE, 5 * METERS_PER_MILE, 600, DEPART, 25)
    assert [c.mile for c in cps] == [0, 5]


@pytest.mark.parametrize("bad", [0, -10])
def test_rejects_non_positive_interval(bad):
    with pytest.raises(ValueError):
        generate_checkpoints(LINE, LINE_M, 3600, DEPART, bad)


def test_rejects_degenerate_geometry():
    with pytest.raises(ValueError):
        generate_checkpoints([[1.0, 1.0]], 1000, 60, DEPART, 25)
    with pytest.raises(ValueError):
        generate_checkpoints([[1.0, 1.0], [1.0, 1.0]], 1000, 60, DEPART, 25)