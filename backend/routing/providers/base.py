"""Provider interfaces. Everything past this package sees domain types, never vendor JSON."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from routing.domain.types import HourlySeries, LatLng, RawRoute


class ProviderError(Exception):
    """Base class. Views map subclasses to the error contract."""


class UpstreamUnavailable(ProviderError):
    """Timeout, 5xx or rate limit from an upstream API after one retry."""


class UpstreamTimeout(UpstreamUnavailable):
    """The upstream did not answer in time (as opposed to answering with an error)."""


class NoRouteFound(ProviderError):
    pass


class GeocodeNotFound(ProviderError):
    pass


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lng: float


class GeocodingProvider(Protocol):
    def search(self, query: str, limit: int) -> list[Place]: ...


class RoutingProvider(Protocol):
    def routes(
        self,
        origin: LatLng,
        dest: LatLng,
        depart_at: datetime,
        gross_weight_lb: int,
        via: LatLng | None = None,
    ) -> list[RawRoute]:
        """Up to 3 routes, primary first. With ``via``, a single route through that point."""
        ...


class WeatherProvider(Protocol):
    max_batch: int

    def hourly(self, points: list[LatLng]) -> list[HourlySeries]:
        """Hourly series per point, same order. At most ``max_batch`` points per call."""
        ...
