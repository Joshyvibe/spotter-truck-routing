"""Nominatim (OpenStreetMap) geocoding fallback. Usage policy: max 1 request/s, real UA.
Results are cached for 30 days by the service layer, so real traffic stays tiny."""

from __future__ import annotations

import threading
import time

import httpx

from .base import GeocodeNotFound, Place, UpstreamUnavailable
from .http import get_json

URL = "https://nominatim.openstreetmap.org/search"
MIN_INTERVAL_S = 1.0  # Nominatim usage policy: at most 1 request per second (DESIGN §2)
_lock = threading.Lock()
_last_call = 0.0


class NominatimGeocoder:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client

    def search(self, query: str, limit: int) -> list[Place]:
        global _last_call
        with _lock:  # one request at a time, spaced at least MIN_INTERVAL_S apart
            wait = _last_call + MIN_INTERVAL_S - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            _last_call = time.monotonic()
        status, body = get_json(
            URL,
            {"q": query, "format": "jsonv2", "limit": limit, "countrycodes": "us,ca"},
            service="nominatim.search",
            client=self.client,
            retries=0,  # a retry would bypass the 1 request/s spacing above
        )
        if status != 200:
            raise UpstreamUnavailable(f"nominatim returned {status}")
        places = [Place(r["display_name"], float(r["lat"]), float(r["lon"])) for r in body]
        if not places:
            raise GeocodeNotFound(query)
        return places
