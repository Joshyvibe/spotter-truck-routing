"""Open-Meteo hourly forecast, many locations per request (no API key)."""

from __future__ import annotations

from typing import Any

import httpx

from routing.domain.types import HourlySeries, LatLng

from .base import UpstreamUnavailable
from .http import get_json

URL = "https://api.open-meteo.com/v1/forecast"
# Open-Meteo splits liquid precipitation into ``rain`` (large-scale systems) and ``showers``
# (convective: thunderstorm cells). Both are rain on the road, so the rain rate is their sum.
HOURLY = "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall"
# 1 past day covers "depart now - 1 h" just after midnight GMT. 10 forecast days cover the
# worst case: departure +7 d, a long trip, and the 48 h heatmap (TECHNICAL_DESIGN R8).
PAST_DAYS = 1
FORECAST_DAYS = 10


class OpenMeteoProvider:
    max_batch = 50

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client

    def hourly(self, points: list[LatLng]) -> list[HourlySeries]:
        if not points:
            return []
        status, body = get_json(
            URL,
            {
                "latitude": ",".join(f"{p.lat:.4f}" for p in points),
                "longitude": ",".join(f"{p.lng:.4f}" for p in points),
                "hourly": HOURLY,
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "GMT",
                "timeformat": "unixtime",
                "past_days": PAST_DAYS,
                "forecast_days": FORECAST_DAYS,
            },
            service="openmeteo.forecast",
            client=self.client,
        )
        if status != 200:
            reason = body.get("reason", "") if isinstance(body, dict) else ""
            raise UpstreamUnavailable(f"open-meteo returned {status}: {reason}")
        # One location -> an object; several -> a list in request order.
        items = body if isinstance(body, list) else [body]
        if len(items) != len(points):
            raise UpstreamUnavailable("open-meteo returned a different number of locations")
        return [parse_series(item) for item in items]


def parse_series(item: dict[str, Any]) -> HourlySeries:
    h = item["hourly"]
    return HourlySeries(
        times=[int(t) for t in h["time"]],
        wind_mph=list(h["wind_speed_10m"]),
        gust_mph=list(h["wind_gusts_10m"]),
        rain_in=[_add(r, s) for r, s in zip(h["rain"], h["showers"], strict=True)],
        # Snowfall is new snow in the hour (not snow depth); with precipitation_unit=inch
        # it is already the in/hr rate the table needs.
        snow_in=list(h["snowfall"]),
    )


def _add(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else round(a + b, 3)
