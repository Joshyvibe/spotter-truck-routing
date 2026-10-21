"""Checkpoint placement and ETAs along a route (docs/DESIGN.md §4.1).

- Positions are ``0, N, 2N, ...`` miles plus the destination, with the same ``N`` on every route.
- ETA at distance ``d`` = departure + drive time interpolated on the provider's cumulative
  time profile, so slow city miles and fast highway miles are both respected.
- Each checkpoint owns the miles nearest to it (half the gap on each side), so the
  segment miles of a route add up exactly to the route length.
"""

from __future__ import annotations

from bisect import bisect_right
from datetime import datetime, timedelta

from .types import METERS_PER_MILE, CheckpointPosition, LatLng, RawRoute

ALLOWED_INTERVALS_MI = (10, 25, 50)
# A destination closer than this to the last interval checkpoint is the same checkpoint.
_SAME_POINT_MI = 1e-6


def interp(xs: list[float], ys: list[float], x: float) -> float:
    """Piecewise-linear interpolation of ``ys`` over ascending ``xs``, clamped at the ends."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect_right(xs, x)
    x0, x1 = xs[i - 1], xs[i]
    y0, y1 = ys[i - 1], ys[i]
    if x1 == x0:
        return y1
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def point_at(
    route: RawRoute,
    dist_m: float,
    lats: list[float] | None = None,
    lngs: list[float] | None = None,
) -> LatLng:
    lats = lats if lats is not None else [c.lat for c in route.coords]
    lngs = lngs if lngs is not None else [c.lng for c in route.coords]
    return LatLng(interp(route.cum_dist_m, lats, dist_m), interp(route.cum_dist_m, lngs, dist_m))


def eta_at(route: RawRoute, dist_m: float, depart_at: datetime) -> datetime:
    return depart_at + timedelta(seconds=interp(route.cum_dist_m, route.cum_time_s, dist_m))


def checkpoint_miles(total_mi: float, interval_mi: int) -> list[float]:
    if interval_mi not in ALLOWED_INTERVALS_MI:
        raise ValueError(f"interval_mi must be one of {ALLOWED_INTERVALS_MI}")
    miles: list[float] = []
    m = 0.0
    k = 0
    while m < total_mi - _SAME_POINT_MI:
        miles.append(m)
        k += 1
        m = float(k * interval_mi)
    miles.append(total_mi)
    return miles


def place_checkpoints(
    route: RawRoute, interval_mi: int, depart_at: datetime
) -> list[CheckpointPosition]:
    total_mi = route.distance_m / METERS_PER_MILE
    miles = checkpoint_miles(total_mi, interval_mi)
    last = len(miles) - 1
    lats = [c.lat for c in route.coords]
    lngs = [c.lng for c in route.coords]
    result: list[CheckpointPosition] = []
    for i, mile in enumerate(miles):
        start = 0.0 if i == 0 else (miles[i - 1] + mile) / 2
        end = total_mi if i == last else (mile + miles[i + 1]) / 2
        dist_m = mile * METERS_PER_MILE
        kind = "origin" if i == 0 else "destination" if i == last else "checkpoint"
        result.append(
            CheckpointPosition(
                index=i,
                kind=kind,
                mile=mile,
                point=point_at(route, dist_m, lats, lngs),
                eta=eta_at(route, dist_m, depart_at),
                segment_start_mi=start,
                segment_end_mi=end,
            )
        )
    return result
