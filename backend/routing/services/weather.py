"""Weather lookups with cell dedup, per-cell caching and parallel batches.

Checkpoints are snapped to 0.1° cells (~11 km); the 3 routes overlap a lot, so this removes
many duplicate lookups. Each cell's full hourly series is cached for 60 min, keyed by the cell
and the current forecast hour, so any later plan that crosses the same cell reuses it (R8).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from django.core.cache import cache

from routing.domain.types import HourlySeries, LatLng
from routing.providers.base import WeatherProvider

from .cache import WEATHER_TTL, key

log = logging.getLogger(__name__)

CHECKPOINT_CELL_DEG = 0.1
MAX_WORKERS = 4


def snap(p: LatLng, step: float = CHECKPOINT_CELL_DEG) -> LatLng:
    return LatLng(round(round(p.lat / step) * step, 4), round(round(p.lng / step) * step, 4))


def forecast_hour(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y%m%d%H")


def series_for_cells(
    provider: WeatherProvider, cells: list[LatLng], issued: str | None = None
) -> dict[LatLng, HourlySeries]:
    """Hourly series for each distinct cell. Cache first, then fetch the misses in batches."""
    issued = issued or forecast_hour()
    unique = list(dict.fromkeys(cells))
    # The provider is part of the key so fixture and real forecasts can never mix.
    source = type(provider).__name__
    keys = {c: key("wx", source, issued, c.lat, c.lng) for c in unique}
    cached = cache.get_many(list(keys.values()))
    out: dict[LatLng, HourlySeries] = {c: cached[k] for c, k in keys.items() if k in cached}
    missing = [c for c in unique if c not in out]
    log.info(
        "weather cells", extra={"cells": len(unique), "cache_hits": len(out), "fetch": len(missing)}
    )
    if missing:
        size = provider.max_batch
        batches = [missing[i : i + size] for i in range(0, len(missing), size)]
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(batches))) as pool:
            results = list(pool.map(provider.hourly, batches))
        fetched = {
            c: s
            for batch, res in zip(batches, results, strict=True)
            for c, s in zip(batch, res, strict=True)
        }
        cache.set_many({keys[c]: s for c, s in fetched.items()}, WEATHER_TTL)
        out.update(fetched)
    return out
