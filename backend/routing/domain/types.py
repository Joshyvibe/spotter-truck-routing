"""Value types shared by the domain modules. No I/O, no Django."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum

METERS_PER_MILE = 1609.344


class Level(IntEnum):
    """Risk levels from the brief. The integer value is the index used in ``avg_risk``."""

    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4


# A checkpoint whose ETA has no forecast is UNKNOWN. It is never treated as LOW.
UNKNOWN = "UNKNOWN"


def level_name(level: Level | None) -> str:
    return UNKNOWN if level is None else level.name


@dataclass(frozen=True)
class LatLng:
    lat: float
    lng: float


@dataclass(frozen=True)
class RawRoute:
    """A route as the providers hand it over. Vendor JSON never gets past ``providers/``."""

    coords: list[LatLng]  # full polyline
    cum_dist_m: list[float]  # cumulative distance per coord, starts at 0
    cum_time_s: list[float]  # cumulative drive time per coord, starts at 0
    distance_m: float
    duration_s: float


@dataclass(frozen=True)
class HourlySeries:
    """Hourly forecast for one location. ``times`` are unix seconds on the hour, ascending.

    ``rain`` and ``snow`` follow Open-Meteo: the value labelled ``t`` is the total over the
    hour that ends at ``t`` (in/hr). ``wind`` and ``gust`` are instantaneous values at ``t`` (mph).
    """

    times: list[int]
    wind_mph: list[float | None]
    gust_mph: list[float | None]
    rain_in: list[float | None]
    snow_in: list[float | None]


@dataclass(frozen=True)
class WeatherSample:
    """Weather for one place at one moment. ``None`` means the forecast does not cover it."""

    wind_mph: float | None
    gust_mph: float | None
    rain_in: float | None
    snow_in: float | None

    @property
    def is_complete(self) -> bool:
        return None not in (self.wind_mph, self.rain_in, self.snow_in)


@dataclass(frozen=True)
class CheckpointPosition:
    """Where a checkpoint sits on a route and when the truck gets there."""

    index: int
    kind: str  # "origin" | "checkpoint" | "destination"
    mile: float
    point: LatLng
    eta: datetime
    segment_start_mi: float  # the checkpoint owns the miles nearest to it
    segment_end_mi: float

    @property
    def segment_mi(self) -> float:
        return self.segment_end_mi - self.segment_start_mi


@dataclass(frozen=True)
class Assessment:
    level: Level | None  # None = UNKNOWN
    driver: str  # "wind" | "rain" | "snow" | "load" | "none" | "unknown"
    reason: str
