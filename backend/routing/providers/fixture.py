"""Offline providers for tests and as an emergency demo fallback (``*_PROVIDER=fixture``).

Weather replays a recorded real Open-Meteo snapshot (see ``FixtureWeatherProvider``). Routes
and geocoding are simple stand-ins used by the API tests ("fake providers", DESIGN §9).
"""

from __future__ import annotations

import gzip
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from routing.domain.geometry import cumulative_distances
from routing.domain.types import METERS_PER_MILE, HourlySeries, LatLng, RawRoute

from .base import GeocodeNotFound, Place

HOUR_S = 3600

CITIES = {
    "chicago, il": Place("Chicago, IL, USA", 41.8781, -87.6298),
    "denver, co": Place("Denver, CO, USA", 39.7392, -104.9903),
    "salt lake city, ut": Place("Salt Lake City, UT, USA", 40.7608, -111.8910),
    "dallas, tx": Place("Dallas, TX, USA", 32.7767, -96.7970),
    "kansas city, mo": Place("Kansas City, MO, USA", 39.0997, -94.5786),
}


class FixtureGeocoder:
    def search(self, query: str, limit: int) -> list[Place]:
        q = query.strip().lower()
        hits = [p for key, p in CITIES.items() if key.startswith(q) or q in key]
        if not hits:
            raise GeocodeNotFound(query)
        return hits[:limit]


class FixtureRoutingProvider:
    """Three bowed lines between the endpoints: straight, north and south. City miles at
    the ends are slower than highway miles in the middle, so ETAs are not linear."""

    BOWS = (0.0, 0.12, -0.12)  # fraction of trip length

    def routes(
        self,
        origin: LatLng,
        dest: LatLng,
        depart_at: datetime,
        gross_weight_lb: int,
        via: LatLng | None = None,
    ) -> list[RawRoute]:
        bows = (0.08,) if via else self.BOWS
        return [_bowed_route(origin, dest, bow) for bow in bows]


def _bowed_route(a: LatLng, b: LatLng, bow: float, n: int = 300) -> RawRoute:
    dlat, dlng = b.lat - a.lat, b.lng - a.lng
    coords = []
    for i in range(n):
        t = i / (n - 1)
        off = bow * math.sin(math.pi * t)
        coords.append(LatLng(a.lat + dlat * t - dlng * off, a.lng + dlng * t + dlat * off))
    cum = cumulative_distances(coords)
    times = [0.0]
    for d0, d1 in zip(cum, cum[1:], strict=False):
        mid_mi = (d0 + d1) / 2 / METERS_PER_MILE
        near_city = mid_mi < 15 or (cum[-1] / METERS_PER_MILE - mid_mi) < 15
        mph = 30 if near_city else 60
        times.append(times[-1] + (d1 - d0) / (mph * METERS_PER_MILE / HOUR_S))
    return RawRoute(coords, cum, times, cum[-1], times[-1])


@dataclass(frozen=True)
class Grid:
    lats: tuple[float, ...]
    lngs: tuple[float, ...]
    step: float


# 2° grid over the contiguous US: 13 latitudes × 30 longitudes = 390 recorded points.
GRID = Grid(
    lats=tuple(float(v) for v in range(25, 50, 2)),
    lngs=tuple(float(v) for v in range(-125, -66, 2)),
    step=2.0,
)
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "openmeteo_us_grid.json.gz"


@lru_cache(maxsize=1)
def _recording() -> dict[str, Any]:
    with gzip.open(FIXTURE_PATH, "rt", encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


class FixtureWeatherProvider:
    """Replays one recorded real Open-Meteo snapshot (docs/DESIGN.md §2, §8: "recorded
    fixture"). Each point reads its nearest recorded grid cell. The recording is re-timed so
    it starts one day before the current hour, which keeps "depart now" plans, the 48 h
    heatmap and trips of about two days inside the recorded window; later hours are UNKNOWN.
    Record a fresh snapshot with ``manage.py record_weather_fixture``.
    """

    max_batch = 50

    def __init__(self, anchor: datetime | None = None) -> None:
        self.anchor = anchor  # fixed time for tests; None = re-time on every call

    def _times(self) -> list[int]:
        now = self.anchor or datetime.now(UTC)
        start = now.replace(minute=0, second=0, microsecond=0) - timedelta(days=1)
        return [int(start.timestamp()) + h * HOUR_S for h in range(_recording()["hours"])]

    def hourly(self, points: list[LatLng]) -> list[HourlySeries]:
        rec = _recording()
        times = self._times()  # the provider lives for the whole process, so not in __init__
        out = []
        for p in points:
            i = self._cell(p)
            out.append(
                HourlySeries(times, rec["wind"][i], rec["gust"][i], rec["rain"][i], rec["snow"][i])
            )
        return out

    @staticmethod
    def _cell(p: LatLng) -> int:
        """Index of the nearest recorded grid point (clamped to the grid's edges)."""

        def nearest(v: float, axis: tuple[float, ...]) -> int:
            k = round((v - axis[0]) / GRID.step)
            return min(max(k, 0), len(axis) - 1)

        return nearest(p.lat, GRID.lats) * len(GRID.lngs) + nearest(p.lng, GRID.lngs)
