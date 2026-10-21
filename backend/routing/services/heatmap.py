"""Corridor heatmap for hours 0–48 after departure (docs/DESIGN.md §4.5, TECHNICAL_DESIGN §3.4).

Built from the stored plan, so a shared link can rebuild it. Every cell uses the *same*
load-aware ``assess()`` as the checkpoints, and the same ETA-alignment rules (wind
interpolated, precipitation from the hour containing the time).

The response is column-shaped (``[hour][point]``), not one object per point per hour, so
~400 points × 49 hours × 4 layers stays around 300–400 KB raw and ~60–80 KB gzipped. The
browser fetches it once and the slider never calls the server again.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import polyline
from django.core.cache import cache

from routing.domain.corridor import corridor_grid
from routing.domain.risk import assess
from routing.domain.types import LatLng
from routing.domain.weather_at_eta import sample_at
from routing.providers.base import WeatherProvider

from .cache import HEATMAP_TTL, key, log_lookup
from .weather import forecast_hour, series_for_cells

log = logging.getLogger(__name__)

HOURS = 49  # 0..48 inclusive
LAYERS = ("risk", "wind", "precip", "snow")


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _r(v: float | None, nd: int) -> float | None:
    return None if v is None else round(v, nd)


def heatmap_cache_key(plan_id: str, issued: str) -> str:
    return key("heatmap", plan_id, issued)


def build_heatmap(plan_id: str, result: dict[str, Any], weather: WeatherProvider) -> dict[str, Any]:
    """Full grid for a stored plan result. Cached per plan and forecast hour."""
    issued = forecast_hour()
    ck = heatmap_cache_key(plan_id, issued)
    hit = cache.get(ck)
    log_lookup("heatmap", hit is not None)
    if hit is not None:
        return hit  # type: ignore[no-any-return]

    started = time.perf_counter()
    routes = [
        [LatLng(lat, lng) for lat, lng in polyline.decode(r["geometry"], 5)]
        for r in result["routes"]
    ]
    step, points = corridor_grid(routes)
    series = series_for_cells(weather, points, issued)
    load_lb = int(result["load_lb"])
    start = datetime.fromisoformat(result["depart_at"].replace("Z", "+00:00"))

    risk: list[list[int | None]] = []
    wind: list[list[float | None]] = []
    precip: list[list[float | None]] = []
    snow: list[list[float | None]] = []
    for h in range(HOURS):
        t = start + timedelta(hours=h)
        r_row: list[int | None] = []
        w_row: list[float | None] = []
        p_row: list[float | None] = []
        s_row: list[float | None] = []
        for p in points:
            sample = sample_at(series[p], t)
            level = assess(sample, load_lb).level
            r_row.append(None if level is None else int(level))
            w_row.append(_r(sample.wind_mph, 1))
            p_row.append(_r(sample.rain_in, 2))
            s_row.append(_r(sample.snow_in, 2))
        risk.append(r_row)
        wind.append(w_row)
        precip.append(p_row)
        snow.append(s_row)

    lats = [p.lat for p in points] or [0.0]
    lngs = [p.lng for p in points] or [0.0]
    body: dict[str, Any] = {
        "plan_id": plan_id,
        "start": _iso(start),
        "hours": HOURS,
        "forecast_as_of": _iso(datetime.strptime(issued, "%Y%m%d%H").replace(tzinfo=UTC)),
        "grid_step_deg": step,
        "bbox": [min(lngs), min(lats), max(lngs), max(lats)],
        "points": [[p.lat, p.lng] for p in points],
        "risk": risk,
        "wind": wind,
        "precip": precip,
        "snow": snow,
    }
    cache.set(ck, body, HEATMAP_TTL)
    log.info(
        "heatmap built",
        extra={
            "plan_id": plan_id,
            "points": len(points),
            "step_deg": step,
            "ms": round((time.perf_counter() - started) * 1000),
        },
    )
    return body


def select_layers(body: dict[str, Any], layer: str) -> dict[str, Any]:
    """``layer=all`` (default) returns every layer; a single name returns only that one."""
    if layer == "all":
        return body
    return {k: v for k, v in body.items() if k not in LAYERS or k == layer}
