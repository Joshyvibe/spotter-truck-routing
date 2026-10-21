"""TomTom Search (geocoding) and Calculate Route (truck profile).

``cum_time_s`` is built from the guidance instructions: each instruction gives a point index
on the polyline and the cumulative ``travelTimeInSeconds`` to it. Between instructions, time is
interpolated by distance. This keeps slow city sections slow and fast highway sections fast.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from routing.domain.checkpoints import interp
from routing.domain.geometry import cumulative_distances
from routing.domain.types import LatLng, RawRoute

from .base import GeocodeNotFound, NoRouteFound, Place, ProviderError, UpstreamTimeout
from .http import get_json

log = logging.getLogger(__name__)

BASE = "https://api.tomtom.com"
LB_TO_KG = 0.45359237
# The 3-route call (primary + 2 alternatives) usually answers in ~4 s, but near-term
# departures have taken 13–31 s in testing (a single route takes ~1 s). It gets one attempt
# and a hard wall-clock deadline. Past it, we use the primary route and the service fills the
# other options through via points: the same "fewer than 3 routes" path as DESIGN.md §2.
# (httpx's read timeout is per chunk, so a slowly streaming answer never trips it alone.)
ALTERNATIVES_DEADLINE_S = 8.0
ALTERNATIVES_TIMEOUT = httpx.Timeout(20.0, connect=3.0)


class TomTomProvider:
    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        if not api_key:
            raise ValueError("TOMTOM_API_KEY is not set")
        self.key = api_key
        self.client = client

    # --- geocoding -------------------------------------------------------------------------
    def search(self, query: str, limit: int) -> list[Place]:
        status, body = get_json(
            f"{BASE}/search/2/search/{quote(query, safe='')}.json",
            {
                "key": self.key,
                "limit": limit,
                "countrySet": "US,CA",
                "typeahead": "true",
                "idxSet": "Geo,PAD,Addr,Str",
            },
            service="tomtom.search",
            client=self.client,
        )
        if status != 200:
            raise ProviderError(f"tomtom.search returned {status}")
        places = [
            Place(
                label=r["address"].get("freeformAddress") or r.get("poi", {}).get("name", ""),
                lat=r["position"]["lat"],
                lng=r["position"]["lon"],
            )
            for r in body.get("results", [])
        ]
        if not places:
            raise GeocodeNotFound(query)
        return places

    # --- routing ---------------------------------------------------------------------------
    def routes(
        self,
        origin: LatLng,
        dest: LatLng,
        depart_at: datetime,
        gross_weight_lb: int,
        via: LatLng | None = None,
    ) -> list[RawRoute]:
        if via:
            return self._calculate(origin, dest, depart_at, gross_weight_lb, via, alternatives=0)
        # A dedicated thread per call, so a request abandoned at the deadline never makes the
        # next plan wait in a queue. The abandoned HTTP call finishes on its own; its answer
        # is ignored (the request was already sent, so no extra quota is used).
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tomtom")
        future = pool.submit(
            self._calculate,
            origin,
            dest,
            depart_at,
            gross_weight_lb,
            None,
            alternatives=2,
            timeout=ALTERNATIVES_TIMEOUT,
            retries=0,
        )
        try:
            result = future.result(timeout=ALTERNATIVES_DEADLINE_S)
            pool.shutdown(wait=False)
            return result
        except (FuturesTimeout, UpstreamTimeout):
            pool.shutdown(wait=False)
            # Only slowness falls back. A 4xx/5xx would fail again, so it is not worth a
            # second request against the free-tier quota. A request past the deadline is
            # left to finish in the background; its answer is ignored.
            log.warning("tomtom alternatives too slow; using the primary route + via fill")
            return self._calculate(origin, dest, depart_at, gross_weight_lb, None, alternatives=0)

    def _calculate(
        self,
        origin: LatLng,
        dest: LatLng,
        depart_at: datetime,
        gross_weight_lb: int,
        via: LatLng | None,
        *,
        alternatives: int,
        timeout: httpx.Timeout | None = None,
        retries: int = 1,
    ) -> list[RawRoute]:
        stops = [origin, *([via] if via else []), dest]
        locations = ":".join(f"{p.lat:.6f},{p.lng:.6f}" for p in stops)
        now = datetime.now(UTC)
        params: dict[str, Any] = {
            "key": self.key,
            "travelMode": "truck",
            "vehicleCommercial": "true",
            "vehicleWeight": round(gross_weight_lb * LB_TO_KG),
            # TomTom rejects departure times in the past.
            "departAt": "now" if depart_at <= now else depart_at.isoformat(timespec="seconds"),
            # Live traffic only describes "right now", which barely matters for a trip that
            # leaves later and lasts many hours, and it made long truck requests far slower.
            # With traffic=false TomTom still applies historic speeds for the departure day
            # and time ("the effect of historic traffic on effective road speeds is still
            # incorporated" — TomTom Calculate Route docs), so ETAs stay time-of-day aware.
            "traffic": "false",
            "instructionsType": "coded",
            "routeRepresentation": "polyline",
            # Alternatives are not supported with waypoints, so a via request returns one route.
            "maxAlternatives": alternatives,
        }
        if alternatives:
            params["alternativeType"] = "anyRoute"
        status, body = get_json(
            f"{BASE}/routing/1/calculateRoute/{locations}/json",
            params,
            service="tomtom.route",
            client=self.client,
            timeout=timeout,
            retries=retries,
        )
        if status != 200:
            detail = (
                str(body.get("error", {}).get("description", "")) if isinstance(body, dict) else ""
            )
            if status in (400, 404) and (
                "NO_ROUTE" in detail.upper() or "no route" in detail.lower()
            ):
                raise NoRouteFound(detail)
            # Any other 4xx (bad key, quota) will not fix itself on retry.
            raise ProviderError(f"tomtom.route returned {status}: {detail[:200]}")
        routes = [parse_route(r) for r in body.get("routes", [])]
        if not routes:
            raise NoRouteFound("TomTom returned no routes")
        return routes


def parse_route(r: dict[str, Any]) -> RawRoute:
    coords = [LatLng(p["latitude"], p["longitude"]) for leg in r["legs"] for p in leg["points"]]
    summary = r["summary"]
    distance_m = float(summary["lengthInMeters"])
    duration_s = float(summary["travelTimeInSeconds"])

    # Haversine shape, scaled so the last value equals TomTom's own length exactly.
    raw = cumulative_distances(coords)
    scale = distance_m / raw[-1] if raw[-1] > 0 else 1.0
    cum_dist = [d * scale for d in raw]

    # Time anchors (distance, cumulative seconds) from the instruction points.
    anchors: dict[int, float] = {0: 0.0, len(coords) - 1: duration_s}
    for ins in r.get("guidance", {}).get("instructions", []):
        idx = ins.get("pointIndex")
        if idx is not None and 0 < idx < len(coords) - 1:
            anchors[idx] = float(ins["travelTimeInSeconds"])
    idxs = sorted(anchors)
    xs = [cum_dist[i] for i in idxs]
    ts: list[float] = []
    for i in idxs:  # enforce monotonic time even if the vendor data is not
        ts.append(max(anchors[i], ts[-1] if ts else 0.0))
    # With no instructions this reduces to distance x average speed (documented fallback).
    cum_time = [interp(xs, ts, d) for d in cum_dist]
    return RawRoute(coords, cum_dist, cum_time, distance_m, duration_s)
