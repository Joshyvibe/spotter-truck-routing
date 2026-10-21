from datetime import timedelta

import pytest

from routing.domain.checkpoints import checkpoint_miles, interp, place_checkpoints
from routing.domain.types import METERS_PER_MILE, LatLng, RawRoute

from .conftest import straight_route


@pytest.mark.parametrize(
    ("total", "interval", "expected"),
    [
        (100, 25, [0, 25, 50, 75, 100]),
        (110, 25, [0, 25, 50, 75, 100, 110]),  # short last gap still gets the destination
        (100, 50, [0, 50, 100]),
        (35, 10, [0, 10, 20, 30, 35]),
        (8, 10, [0, 8]),  # trip shorter than one interval
    ],
)
def test_positions_include_origin_and_destination(total, interval, expected):
    assert checkpoint_miles(total, interval) == pytest.approx(expected)


@pytest.mark.parametrize("interval", [10, 25, 50])
def test_count_for_1000_miles(interval):
    assert len(checkpoint_miles(1000, interval)) == 1000 // interval + 1


def test_rejects_interval_outside_brief():
    with pytest.raises(ValueError):
        checkpoint_miles(100, 20)


@pytest.mark.parametrize("interval", [10, 25, 50])
@pytest.mark.parametrize("miles", [8.0, 100.0, 333.3, 1003.4])
def test_segment_miles_sum_to_route_length(interval, miles, depart):
    cps = place_checkpoints(straight_route(miles), interval, depart)
    assert sum(c.segment_mi for c in cps) == pytest.approx(miles)
    # contiguous, no gaps or overlaps
    for a, b in zip(cps, cps[1:], strict=False):
        assert a.segment_end_mi == pytest.approx(b.segment_start_mi)


def test_midpoint_ownership_matches_worked_example(depart):
    # 100 mi every 25 mi: the ends own 12.5 mi, the middle ones 25 mi (research note).
    cps = place_checkpoints(straight_route(100), 25, depart)
    assert [c.segment_mi for c in cps] == pytest.approx([12.5, 25, 25, 25, 12.5])
    assert [c.kind for c in cps] == [
        "origin",
        "checkpoint",
        "checkpoint",
        "checkpoint",
        "destination",
    ]


def test_eta_uses_cumulative_time_profile(depart):
    cps = place_checkpoints(straight_route(100, mph=50), 25, depart)
    assert [c.eta - depart for c in cps] == [timedelta(minutes=m) for m in (0, 30, 60, 90, 120)]


def test_eta_respects_slow_and_fast_sections(depart):
    # First 50 mi at 25 mph (city), next 50 mi at 75 mph (highway).
    m = METERS_PER_MILE
    coords = [LatLng(40, -100), LatLng(40.7, -100), LatLng(41.4, -100)]
    route = RawRoute(coords, [0, 50 * m, 100 * m], [0, 7200, 9600], 100 * m, 9600)
    cps = place_checkpoints(route, 25, depart)
    assert [(c.eta - depart).total_seconds() for c in cps] == pytest.approx(
        [0, 3600, 7200, 8400, 9600]
    )


def test_etas_are_monotonic(depart):
    cps = place_checkpoints(straight_route(1003.4), 10, depart)
    assert all(a.eta <= b.eta for a, b in zip(cps, cps[1:], strict=False))


def test_point_is_interpolated_on_polyline(depart):
    cps = place_checkpoints(straight_route(100), 50, depart)
    mid = cps[1].point
    assert mid.lng == pytest.approx(-100)
    assert mid.lat == pytest.approx((cps[0].point.lat + cps[2].point.lat) / 2, abs=1e-3)


def test_interp_clamps():
    assert interp([0, 10], [5, 15], -1) == 5
    assert interp([0, 10], [5, 15], 11) == 15
    assert interp([0, 10], [5, 15], 2.5) == 7.5
