import pytest

from routing.domain.corridor import corridor_grid
from routing.domain.geometry import cumulative_distances, haversine_m, simplify, slice_by_distance
from routing.domain.segments import merge_runs
from routing.domain.types import LatLng, Level


def test_haversine_one_degree_lat():
    assert haversine_m(LatLng(40, -100), LatLng(41, -100)) == pytest.approx(111_195, rel=1e-3)


def test_slice_by_distance_interpolates_ends():
    coords = [LatLng(0, 0), LatLng(1, 0), LatLng(2, 0)]
    cum = cumulative_distances(coords)
    part = slice_by_distance(coords, cum, cum[1] / 2, cum[1] * 1.5)
    assert part[0].lat == pytest.approx(0.5)
    assert part[1] == LatLng(1, 0)
    assert part[-1].lat == pytest.approx(1.5)


def test_simplify_drops_collinear_points():
    coords = [LatLng(40 + i * 0.001, -100) for i in range(1000)]
    assert len(simplify(coords)) == 2


def test_merge_runs():
    runs = merge_runs(
        [
            (0, 12.5, Level.LOW),
            (12.5, 37.5, Level.LOW),
            (37.5, 62.5, Level.HIGH),
            (62.5, 87.5, None),
            (87.5, 100, None),
        ]
    )
    assert [(r.from_mi, r.to_mi, r.level) for r in runs] == [
        (0, 37.5, Level.LOW),
        (37.5, 62.5, Level.HIGH),
        (62.5, 100, None),
    ]


def test_corridor_grid_is_bounded_and_on_fixed_lattice():
    # ~1,000 mi east-west route: Chicago-ish to Denver-ish
    line = [LatLng(41.8 - 0.002 * i, -87.6 - 0.0173 * i) for i in range(1000)]
    step, pts = corridor_grid([line])
    assert 0 < len(pts) <= 400
    assert all(abs(p.lat / step - round(p.lat / step)) < 1e-6 for p in pts)
    # every point is within ~40 km (+ half a cell) of the route
    assert all(min(haversine_m(p, q) for q in line[::10]) < 60_000 for p in pts)


def test_corridor_widens_step_when_too_many_points():
    line = [LatLng(30 + 0.02 * i, -120 + 0.04 * i) for i in range(1000)]
    step, pts = corridor_grid([line], max_points=100)
    assert step > 0.25
    assert len(pts) <= 100
