"""Cache keys and TTLs in one place (docs/DESIGN.md §8)."""

from __future__ import annotations

import hashlib
import logging

log = logging.getLogger(__name__)

GEOCODE_TTL = 30 * 24 * 3600
ROUTES_TTL = 10 * 60
WEATHER_TTL = 60 * 60
HEATMAP_TTL = 10 * 60


def key(*parts: object) -> str:
    raw = ":".join(str(p) for p in parts)
    # Redis keys stay short and safe whatever the input text is.
    return f"v1:{parts[0]}:{hashlib.sha1(raw.encode()).hexdigest()}"


def log_lookup(name: str, hit: bool) -> None:
    """One line per cache lookup: TECHNICAL_DESIGN §3.11 asks for cache hit/miss in logs."""
    log.info("cache lookup", extra={"cache": name, "hit": hit})
