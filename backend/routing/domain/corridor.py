"""Heatmap corridor grid (docs/DESIGN.md §4.5, TECHNICAL_DESIGN R8).

Corridor = union of the route lines, buffered by ~40 km. Grid points sit on a *fixed global
lattice* (multiples of the step in degrees), so two plans in the same region produce the same
points and share the weather cache. The step starts at 0.25° and widens until the grid has at
most ``max_points`` points, which bounds both the response size and the weather-API quota.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from shapely import MultiLineString, Point
from shapely.prepared import prep

from .geometry import LocalProjection, simplify
from .types import LatLng

CORRIDOR_BUFFER_M = 40_000.0
BASE_STEP_DEG = 0.25
MAX_POINTS = 400


def corridor_grid(
    routes: Sequence[Sequence[LatLng]],
    buffer_m: float = CORRIDOR_BUFFER_M,
    max_points: int = MAX_POINTS,
    base_step_deg: float = BASE_STEP_DEG,
) -> tuple[float, list[LatLng]]:
    """Return ``(step_deg, points)`` for the corridor around ``routes``."""
    all_pts = [p for r in routes for p in r]
    if not all_pts:
        return base_step_deg, []
    proj = LocalProjection(sum(p.lat for p in all_pts) / len(all_pts))
    # Simplifying to 1 km first keeps the buffer fast; it cannot move the line by more than
    # 1 km, which is small next to a 40 km buffer.
    lines = [[proj.forward(p) for p in simplify(r, 1_000.0)] for r in routes if len(r) >= 2]
    corridor = MultiLineString(lines).buffer(buffer_m, quad_segs=8)
    inside = prep(corridor)
    min_x, min_y, max_x, max_y = corridor.bounds
    sw, ne = proj.inverse(min_x, min_y), proj.inverse(max_x, max_y)

    step = base_step_deg
    while True:
        points = [p for p in _lattice(sw, ne, step) if inside.contains(Point(*proj.forward(p)))]
        if len(points) <= max_points:
            return step, points
        step += base_step_deg


def _lattice(sw: LatLng, ne: LatLng, step: float) -> list[LatLng]:
    i0, i1 = math.ceil(sw.lat / step), math.floor(ne.lat / step)
    j0, j1 = math.ceil(sw.lng / step), math.floor(ne.lng / step)
    return [
        LatLng(round(i * step, 4), round(j * step, 4))
        for i in range(i0, i1 + 1)
        for j in range(j0, j1 + 1)
    ]
