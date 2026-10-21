"""OSRM public demo, fallback only: no truck profile, sometimes fewer than 3 routes."""

from __future__ import annotations

from datetime import datetime
from itertools import accumulate
from typing import Any

import httpx

from routing.domain.types import LatLng, RawRoute

from .base import NoRouteFound, UpstreamUnavailable
from .http import get_json

BASE = "https://router.project-osrm.org/route/v1/driving"


class OsrmProvider:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client

    def routes(
        self,
        origin: LatLng,
        dest: LatLng,
        depart_at: datetime,
        gross_weight_lb: int,
        via: LatLng | None = None,
    ) -> list[RawRoute]:
        stops = [origin, *([via] if via else []), dest]
        coords = ";".join(f"{p.lng:.6f},{p.lat:.6f}" for p in stops)
        status, body = get_json(
            f"{BASE}/{coords}",
            {
                "alternatives": "false" if via else "3",
                "overview": "full",
                "geometries": "geojson",
                "annotations": "duration,distance",
            },
            service="osrm.route",
            client=self.client,
        )
        if status != 200 or body.get("code") != "Ok":
            if isinstance(body, dict) and body.get("code") == "NoRoute":
                raise NoRouteFound("OSRM found no route")
            raise UpstreamUnavailable(f"osrm returned {status}")
        return [parse_route(r) for r in body["routes"][:3]]


def parse_route(r: dict[str, Any]) -> RawRoute:
    coords = [LatLng(lat, lng) for lng, lat in r["geometry"]["coordinates"]]
    dists = [d for leg in r["legs"] for d in leg["annotation"]["distance"]]
    durs = [d for leg in r["legs"] for d in leg["annotation"]["duration"]]
    # Multi-leg responses repeat the shared point; annotations have one entry per segment.
    n = min(len(coords) - 1, len(dists))
    coords = coords[: n + 1]
    cum_dist = [0.0, *accumulate(dists[:n])]
    cum_time = [0.0, *accumulate(durs[:n])]
    return RawRoute(coords, cum_dist, cum_time, cum_dist[-1], cum_time[-1])
