"""Pick providers from settings (one env var swaps a vendor)."""

from __future__ import annotations

from functools import cache

from django.conf import settings

from .base import GeocodingProvider, RoutingProvider, WeatherProvider


@cache
def routing_provider() -> RoutingProvider:
    match settings.ROUTING_PROVIDER:
        case "tomtom":
            from .tomtom import TomTomProvider

            return TomTomProvider(settings.TOMTOM_API_KEY)
        case "osrm":
            from .osrm import OsrmProvider

            return OsrmProvider()
        case "fixture":
            from .fixture import FixtureRoutingProvider

            return FixtureRoutingProvider()
    raise ValueError(f"unknown ROUTING_PROVIDER {settings.ROUTING_PROVIDER!r}")


@cache
def geocoding_provider() -> GeocodingProvider:
    if settings.ROUTING_PROVIDER == "fixture":
        from .fixture import FixtureGeocoder

        return FixtureGeocoder()
    if settings.TOMTOM_API_KEY:
        from .tomtom import TomTomProvider

        return TomTomProvider(settings.TOMTOM_API_KEY)
    from .nominatim import NominatimGeocoder

    return NominatimGeocoder()


@cache
def weather_provider() -> WeatherProvider:
    match settings.WEATHER_PROVIDER:
        case "openmeteo":
            from .openmeteo import OpenMeteoProvider

            return OpenMeteoProvider()
        case "fixture":
            from .fixture import FixtureWeatherProvider

            return FixtureWeatherProvider()
    raise ValueError(f"unknown WEATHER_PROVIDER {settings.WEATHER_PROVIDER!r}")
