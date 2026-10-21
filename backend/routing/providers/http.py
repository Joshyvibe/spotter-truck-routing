"""Shared HTTP client: tight timeouts and exactly one retry with jitter (no retry storms)."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx

from .base import UpstreamTimeout, UpstreamUnavailable

log = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(10.0, connect=3.0)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

_client = httpx.Client(timeout=TIMEOUT, headers={"User-Agent": "spotter-truck-routing/1.0"})


def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    service: str,
    client: httpx.Client | None = None,
    timeout: httpx.Timeout | None = None,
    retries: int = 1,
) -> tuple[int, Any]:
    """GET and decode JSON. Returns ``(status, body)`` for any non-retryable status, so the
    caller can read vendor 4xx errors. Raises ``UpstreamUnavailable`` once the retries on a
    timeout, 429 or 5xx are spent. ``retries=0`` suits slow calls where a retry would only
    double the wait."""
    c = client or _client
    last = retries + 1
    for attempt in range(1, last + 1):
        started = time.perf_counter()
        try:
            resp = c.get(url, params=params, timeout=timeout or c.timeout)
        except httpx.TransportError as exc:
            log.warning(
                "upstream error",
                extra={"service": service, "attempt": attempt, "error": type(exc).__name__},
            )
            if attempt == last:
                if isinstance(exc, httpx.TimeoutException):
                    raise UpstreamTimeout(f"{service} timed out") from exc
                raise UpstreamUnavailable(f"{service} unreachable") from exc
        else:
            ms = round((time.perf_counter() - started) * 1000)
            log.info(
                "upstream call",
                extra={
                    "service": service,
                    "status": resp.status_code,
                    "ms": ms,
                    "attempt": attempt,
                },
            )
            if resp.status_code not in RETRYABLE_STATUS:
                try:
                    return resp.status_code, resp.json()
                except ValueError as exc:
                    raise UpstreamUnavailable(f"{service} returned invalid JSON") from exc
            if attempt == last:
                raise UpstreamUnavailable(f"{service} returned {resp.status_code}")
        time.sleep(0.2 + random.random() * 0.4)
    raise AssertionError("unreachable")
