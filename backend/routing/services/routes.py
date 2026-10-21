"""Get 3 distinct route options (docs/DESIGN.md §2).

TomTom returns up to 3 routes in one call. For short or very direct trips it can return fewer.
Then we ask again through a via point offset ~12% of the route length to each side of the
midpoint, and drop near-duplicates (> 90% shared geometry). We never invent a route: if there
are still fewer than 3, the caller shows what exists plus a warning.
"""

from __future__ import annotations

import math
from datetime import datetime

from django.core.cache import cache

from routing.domain.geometry import LocalProjection, shared_fraction
from routing.domain.types import LatLng, RawRoute
from routing.providers.base import NoRouteFound, ProviderError, RoutingProvider

from .cache import ROUTES_TTL, key, log_lookup

TARGET_ROUTES = 3
VIA_OFFSET_FRACTION = 0.12
DUPLICATE_SHARE = 0.90
LOAD_BUCKET_LB = 5_000


def route_cache_key(
    source: str, origin: LatLng, dest: LatLng, depart_at: datetime, gross_lb: int
) -> str:
    slot = int(depart_at.timestamp() // 900)  # 15-minute departure buckets
    bucket = gross_lb // LOAD_BUCKET_LB
    # The provider is part of the key so fixture and real routes can never mix.
    return key(
        "routes",
        source,
        round(origin.lat, 3),
        round(origin.lng, 3),
        round(dest.lat, 3),
        round(dest.lng, 3),
        slot,
        bucket,
    )


def get_routes(
    provider: RoutingProvider, origin: LatLng, dest: LatLng, depart_at: datetime, gross_lb: int
) -> list[RawRoute]:
    ck = route_cache_key(type(provider).__name__, origin, dest, depart_at, gross_lb)
    hit = cache.get(ck)
    log_lookup("routes", hit is not None)
    if hit is not None:
        return hit  # type: ignore[no-any-return]
    routes = _distinct(provider.routes(origin, dest, depart_at, gross_lb))
    degraded = False  # a via call failed for a transient reason: show the result, don't cache it
    if len(routes) < TARGET_ROUTES:
        for via in via_points(routes[0]):
            try:
                extra = provider.routes(origin, dest, depart_at, gross_lb, via=via)
            except NoRouteFound:
                continue
            except ProviderError:
                degraded = True
                continue
            routes = _distinct(routes + extra)
            if len(routes) >= TARGET_ROUTES:
                break
    routes = routes[:TARGET_ROUTES]
    if not degraded:
        cache.set(ck, routes, ROUTES_TTL)
    return routes


def _distinct(routes: list[RawRoute]) -> list[RawRoute]:
    kept: list[RawRoute] = []
    for r in routes:
        if all(shared_fraction(r.coords, k.coords) <= DUPLICATE_SHARE for k in kept):
            kept.append(r)
    return kept


def via_points(route: RawRoute) -> list[LatLng]:
    """Two points either side of the route midpoint, perpendicular to the overall heading."""
    a, b = route.coords[0], route.coords[-1]
    mid = route.coords[len(route.coords) // 2]
    proj = LocalProjection(mid.lat)
    ax, ay = proj.forward(a)
    bx, by = proj.forward(b)
    mx, my = proj.forward(mid)
    length = math.hypot(bx - ax, by - ay) or 1.0
    nx, ny = -(by - ay) / length, (bx - ax) / length  # unit normal
    off = VIA_OFFSET_FRACTION * route.distance_m
    return [proj.inverse(mx + nx * off * s, my + ny * off * s) for s in (1, -1)]
