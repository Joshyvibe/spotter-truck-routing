"""Give every request an id: echoed in ``X-Request-ID``, the error body and every log line."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

log = logging.getLogger("routing.request")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


class RequestIdMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _SAFE_ID.match(incoming) else f"req_{uuid.uuid4().hex[:20]}"
        request.request_id = request_id  # type: ignore[attr-defined]
        started = time.perf_counter()
        response = self._too_large(request, request_id) or self.get_response(request)
        response["X-Request-ID"] = request_id
        log.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "ms": round((time.perf_counter() - started) * 1000),
            },
        )
        return response

    @staticmethod
    def _too_large(request: HttpRequest, request_id: str) -> HttpResponse | None:
        """Bodies are tiny JSON (TECHNICAL_DESIGN §3.1: max 16 KB). DRF reads the request
        stream itself, which skips Django's own size check, so it is enforced here."""
        try:
            length = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0
        if length <= settings.DATA_UPLOAD_MAX_MEMORY_SIZE:
            return None
        body = {
            "error": {
                "code": "VALIDATION",
                "message": "Request body too large (max 16 KB).",
                "field": None,
                "request_id": request_id,
                "retryable": False,
            }
        }
        return JsonResponse(body, status=400)
