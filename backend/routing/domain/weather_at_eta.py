"""Read a forecast at the truck's ETA (docs/DESIGN.md §4.2).

- Wind and gusts are instantaneous: linear interpolation between the two hours around the ETA.
- Rain and snowfall are totals over the hour ending at their label. The truck is in the hour
  ``[floor(eta), floor(eta) + 1h)``, which is labelled ``floor(eta) + 1h``. For any ETA that
  is not exactly on the hour this equals ``ceil(eta)``. For an ETA exactly on the hour (for
  example the departure checkpoint at 08:00) it takes the 08:00–09:00 total, the hour the
  truck is actually driving, rather than the 07:00–08:00 total before it left.
- An ETA the series does not cover gives ``None`` values, which classify as UNKNOWN.
"""

from __future__ import annotations

from bisect import bisect_left
from datetime import datetime

from .types import HourlySeries, WeatherSample

HOUR_S = 3600


def _index(series: HourlySeries, t: int) -> int | None:
    i = bisect_left(series.times, t)
    if i < len(series.times) and series.times[i] == t:
        return i
    return None


def _instant(series: HourlySeries, values: list[float | None], ts: float) -> float | None:
    h0 = int(ts // HOUR_S) * HOUR_S
    i0 = _index(series, h0)
    if i0 is None:
        return None
    v0 = values[i0]
    if ts == h0:
        return v0
    i1 = _index(series, h0 + HOUR_S)
    if i1 is None:
        return None
    v1 = values[i1]
    if v0 is None or v1 is None:
        return None
    return v0 + (v1 - v0) * (ts - h0) / HOUR_S


def _hour_total(series: HourlySeries, values: list[float | None], ts: float) -> float | None:
    label = int(ts // HOUR_S) * HOUR_S + HOUR_S
    i = _index(series, label)
    return None if i is None else values[i]


def sample_at(series: HourlySeries, when: datetime) -> WeatherSample:
    ts = when.timestamp()
    return WeatherSample(
        wind_mph=_instant(series, series.wind_mph, ts),
        gust_mph=_instant(series, series.gust_mph, ts),
        rain_in=_hour_total(series, series.rain_in, ts),
        snow_in=_hour_total(series, series.snow_in, ts),
    )
