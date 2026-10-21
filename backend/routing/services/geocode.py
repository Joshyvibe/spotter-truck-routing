"""Geocoding with a 30-day cache (place names do not move)."""

from __future__ import annotations

from django.core.cache import cache

from routing.providers.base import GeocodingProvider, Place

from .cache import GEOCODE_TTL, key, log_lookup


def normalise(q: str) -> str:
    return " ".join(q.lower().split())


def search(provider: GeocodingProvider, query: str, limit: int = 5) -> list[Place]:
    ck = key("geocode", type(provider).__name__, normalise(query), limit)
    hit = cache.get(ck)
    log_lookup("geocode", hit is not None)
    if hit is not None:
        return hit  # type: ignore[no-any-return]
    places = provider.search(query, limit)
    cache.set(ck, places, GEOCODE_TTL)
    return places


def resolve(provider: GeocodingProvider, query: str) -> Place:
    """Best match for free text. Raises ``GeocodeNotFound``."""
    return search(provider, query, 1)[0]
