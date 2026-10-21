"""Polyline helpers: distances, slicing by mileage, display simplification.

Distances use the haversine formula. For simplification and corridor buffering we project
to a local equirectangular plane (x = lng * cos(lat0), y = lat, in metres). Over the width
of a US trip the scale error stays within a few percent, which is fine for a 25 m
simplification tolerance and a 40 km corridor, and it avoids a pyproj dependency.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from shapely import LineString

from .types import LatLng

EARTH_RADIUS_M = 6_371_008.8
M_PER_DEG_LAT = 111_320.0


def haversine_m(a: LatLng, b: LatLng) -> float:
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp = p2 - p1
    dl = math.radians(b.lng - a.lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def cumulative_distances(coords: Sequence[LatLng]) -> list[float]:
    out = [0.0]
    for a, b in zip(coords, coords[1:], strict=False):
        out.append(out[-1] + haversine_m(a, b))
    return out


class LocalProjection:
    """Equirectangular projection around a reference latitude, in metres."""

    def __init__(self, ref_lat: float) -> None:
        self.kx = M_PER_DEG_LAT * math.cos(math.radians(ref_lat))
        self.ky = M_PER_DEG_LAT

    def forward(self, p: LatLng) -> tuple[float, float]:
        return p.lng * self.kx, p.lat * self.ky

    def inverse(self, x: float, y: float) -> LatLng:
        return LatLng(y / self.ky, x / self.kx)


def slice_by_distance(
    coords: Sequence[LatLng], cum_dist_m: Sequence[float], start_m: float, end_m: float
) -> list[LatLng]:
    """The part of the polyline between two distances, with interpolated end points."""
    if end_m <= start_m:
        return []

    def at(d: float, i: int) -> LatLng:
        d0, d1 = cum_dist_m[i - 1], cum_dist_m[i]
        t = 0.0 if d1 == d0 else (d - d0) / (d1 - d0)
        a, b = coords[i - 1], coords[i]
        return LatLng(a.lat + (b.lat - a.lat) * t, a.lng + (b.lng - a.lng) * t)

    out: list[LatLng] = []
    n = len(coords)
    i = 1
    while i < n and cum_dist_m[i] <= start_m:
        i += 1
    if i >= n:
        return [coords[-1]]
    out.append(at(start_m, i))
    while i < n and cum_dist_m[i] < end_m:
        out.append(coords[i])
        i += 1
    out.append(coords[-1] if i >= n else at(end_m, i))
    return out


def simplify(coords: Sequence[LatLng], tolerance_m: float = 25.0) -> list[LatLng]:
    """Douglas-Peucker for display. Route maths always uses the full polyline."""
    if len(coords) < 3:
        return list(coords)
    proj = LocalProjection(sum(c.lat for c in coords) / len(coords))
    line = LineString([proj.forward(c) for c in coords]).simplify(
        tolerance_m, preserve_topology=False
    )
    return [proj.inverse(x, y) for x, y in line.coords]


def shared_fraction(
    a: Sequence[LatLng], b: Sequence[LatLng], tolerance_m: float = 1_000.0
) -> float:
    """Share of ``a``'s length that runs within ``tolerance_m`` of ``b`` (duplicate check)."""
    if len(a) < 2 or len(b) < 2:
        return 0.0
    proj = LocalProjection(a[len(a) // 2].lat)
    # 100 m simplification first: cheap, and far below the 1 km tolerance.
    la = LineString([proj.forward(p) for p in simplify(a, 100.0)])
    lb = LineString([proj.forward(p) for p in simplify(b, 100.0)]).buffer(tolerance_m)
    return float(la.intersection(lb).length / la.length) if la.length else 0.0
