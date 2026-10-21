"""Record the weather fixture used by ``WEATHER_PROVIDER=fixture`` (docs/DESIGN.md §2, §8).

One real Open-Meteo snapshot over a 2° grid covering the contiguous US (13 × 30 = 390 points),
1 past day + 3 forecast days, saved as gzipped JSON. Run it rarely: it costs ~390 location
calls of the free Open-Meteo quota.

    uv run python manage.py record_weather_fixture
"""

from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime

from django.core.management.base import BaseCommand

from routing.domain.types import LatLng
from routing.providers.fixture import FIXTURE_PATH, GRID
from routing.providers.http import get_json
from routing.providers.openmeteo import HOURLY, URL, parse_series

BATCH = 50


class Command(BaseCommand):
    help = "Record a real Open-Meteo snapshot as the offline weather fixture"

    def handle(self, *args: object, **opts: object) -> None:
        points = [LatLng(lat, lng) for lat in GRID.lats for lng in GRID.lngs]
        series = []
        for i in range(0, len(points), BATCH):
            batch = points[i : i + BATCH]
            status, body = get_json(
                URL,
                {
                    "latitude": ",".join(f"{p.lat:.2f}" for p in batch),
                    "longitude": ",".join(f"{p.lng:.2f}" for p in batch),
                    "hourly": HOURLY,
                    "wind_speed_unit": "mph",
                    "precipitation_unit": "inch",
                    "timezone": "GMT",
                    "timeformat": "unixtime",
                    "past_days": 1,
                    "forecast_days": 3,
                },
                service="openmeteo.record",
            )
            if status != 200:
                raise SystemExit(f"Open-Meteo returned {status}: {body}")
            series += [parse_series(item) for item in (body if isinstance(body, list) else [body])]
            self.stdout.write(f"recorded {len(series)}/{len(points)}")

        times = series[0].times
        payload = {
            "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "source": "Open-Meteo forecast API (real data, re-timed on replay)",
            "start": times[0],
            "hours": len(times),
            # [point][hour], points ordered lat-major as GRID.lats × GRID.lngs
            "wind": [[_r(v, 1) for v in s.wind_mph] for s in series],
            "gust": [[_r(v, 1) for v in s.gust_mph] for s in series],
            "rain": [[_r(v, 3) for v in s.rain_in] for s in series],
            "snow": [[_r(v, 3) for v in s.snow_in] for s in series],
        }
        with gzip.open(FIXTURE_PATH, "wt", encoding="utf-8") as f:
            json.dump(payload, f, separators=(",", ":"))
        self.stdout.write(f"wrote {FIXTURE_PATH} ({len(points)} points × {len(times)} h)")


def _r(v: float | None, nd: int) -> float | None:
    return None if v is None else round(v, nd)
