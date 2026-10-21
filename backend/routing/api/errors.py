"""One error envelope for every endpoint (docs/DESIGN.md §6 + R6)."""

from __future__ import annotations

import logging
from typing import Any

from rest_framework import exceptions, status
from rest_framework.response import Response

from routing.providers.base import GeocodeNotFound, NoRouteFound, UpstreamUnavailable

log = logging.getLogger(__name__)


def error_response(
    request: Any,
    code: str,
    message: str,
    http_status: int,
    *,
    field: str | None = None,
    retryable: bool = False,
    headers: dict[str, str] | None = None,
) -> Response:
    body = {
        "error": {
            "code": code,
            "message": message,
            "field": field,
            "request_id": getattr(request, "request_id", None),
            "retryable": retryable,
        }
    }
    return Response(body, status=http_status, headers=headers)


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    request = context.get("request")
    if isinstance(exc, NoRouteFound):
        return error_response(
            request, "NO_ROUTE", "No truck route found between these points.", 422
        )
    if isinstance(exc, GeocodeNotFound):
        return error_response(request, "GEOCODE_NOT_FOUND", f"Could not find “{exc}”.", 422)
    if isinstance(exc, UpstreamUnavailable):
        log.warning("upstream unavailable", extra={"detail": str(exc)})
        return error_response(
            request,
            "UPSTREAM_UNAVAILABLE",
            "A routing or weather service is not responding. Please try again.",
            502,
            retryable=True,
        )
    if isinstance(exc, exceptions.ValidationError):
        field, message = _first_error(exc.detail)
        return error_response(request, "VALIDATION", message, 400, field=field)
    if isinstance(exc, exceptions.Throttled):
        wait = int(exc.wait or 60)
        return error_response(
            request,
            "RATE_LIMITED",
            f"Too many requests. Try again in {wait} s.",
            429,
            retryable=True,
            headers={"Retry-After": str(wait)},
        )
    if isinstance(exc, exceptions.NotFound):
        return error_response(request, "NOT_FOUND", "Not found.", 404)
    if isinstance(exc, exceptions.ParseError):
        return error_response(request, "VALIDATION", "Malformed JSON body.", 400)
    if isinstance(exc, exceptions.MethodNotAllowed):
        return error_response(request, "METHOD_NOT_ALLOWED", str(exc.detail), 405)
    if isinstance(exc, exceptions.UnsupportedMediaType):
        return error_response(request, "VALIDATION", "Send JSON (application/json).", 400)
    if isinstance(exc, exceptions.APIException):
        return error_response(request, "VALIDATION", str(exc.detail), 400)
    log.exception("unhandled error", extra={"request_id": getattr(request, "request_id", None)})
    return error_response(
        request, "INTERNAL", "Something went wrong.", status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def _first_error(detail: Any, prefix: str = "") -> tuple[str | None, str]:
    """Flatten DRF's nested error dict to the first ``(field, message)``."""
    if isinstance(detail, dict):
        for key, value in detail.items():
            name = key if key != "non_field_errors" else None
            field, msg = _first_error(value, f"{prefix}{name}" if name else prefix)
            return field or (f"{prefix}{name}" if name else None), msg
    if isinstance(detail, list) and detail:
        return _first_error(detail[0], prefix)
    return (prefix or None), str(detail)
