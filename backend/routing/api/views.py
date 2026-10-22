"""Thin views: validate, call a service, shape the response. Logic lives in services/domain."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.http import HttpRequest, JsonResponse
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from routing.domain.geometry import haversine_m
from routing.domain.types import LatLng
from routing.models import TripPlan
from routing.providers.base import GeocodeNotFound, Place
from routing.providers.registry import geocoding_provider, routing_provider, weather_provider
from routing.services import geocode
from routing.services.heatmap import LAYERS, build_heatmap, select_layers
from routing.services.plan_trip import PlanInputs, plan_trip

from .errors import error_response
from .serializers import GeocodeQuerySerializer, PlanCreateSerializer

MIN_TRIP_M = 1_000


class HealthView(APIView):
    """Liveness check and the SPA warm-up ping. No upstream or DB calls."""

    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


def _plan_body(plan: TripPlan) -> dict[str, Any]:
    return {
        "id": str(plan.id),
        "created_at": plan.created_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        **plan.result,
    }


class PlanListCreateView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "plans"

    def post(self, request: Request) -> Response:
        s = PlanCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        geo = geocoding_provider()
        places: dict[str, Place] = {}
        for field in ("origin", "destination"):
            value = data[field]
            if isinstance(value, dict):
                places[field] = Place(value["label"], value["lat"], value["lng"])
                continue
            try:
                places[field] = geocode.resolve(geo, value)
            except GeocodeNotFound:
                return error_response(
                    request, "GEOCODE_NOT_FOUND", f"Could not find “{value}”.", 422, field=field
                )
        o, d = places["origin"], places["destination"]
        if haversine_m(LatLng(o.lat, o.lng), LatLng(d.lat, d.lng)) < MIN_TRIP_M:
            return error_response(
                request,
                "VALIDATION",
                "Origin and destination must be different places.",
                400,
                field="destination",
            )
        inputs = PlanInputs(o, d, data["depart_at"], data["load_lb"], data["interval_mi"])
        result = plan_trip(inputs, routing_provider(), weather_provider())
        plan = TripPlan.objects.create(
            origin_text=_text(data["origin"]),
            destination_text=_text(data["destination"]),
            origin=result["origin"],
            destination=result["destination"],
            depart_at=inputs.depart_at,
            load_lb=inputs.load_lb,
            interval_mi=inputs.interval_mi,
            forecast_as_of=result["forecast_as_of"],
            result=result,
        )
        return Response(
            _plan_body(plan), status=201, headers={"Location": f"/api/v1/plans/{plan.id}"}
        )


def _text(value: str | dict[str, Any]) -> str:
    return value if isinstance(value, str) else str(value["label"])


def get_plan_or_none(plan_id: str) -> TripPlan | None:
    try:
        uid = UUID(plan_id)
    except ValueError:
        return None
    return TripPlan.objects.filter(pk=uid).first()


class PlanDetailView(APIView):
    def get(self, request: Request, plan_id: str) -> Response:
        plan = get_plan_or_none(plan_id)
        if plan is None:
            return error_response(request, "PLAN_NOT_FOUND", "No plan with this id.", 404)
        return Response(_plan_body(plan), headers={"Cache-Control": "private, max-age=600"})


class PlanHeatmapView(APIView):
    """Column-shaped corridor grid, hours 0–48 after departure. Fetched once per plan."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "heatmap"

    def get(self, request: Request, plan_id: str) -> Response:
        layer = request.query_params.get("layer", "all")
        if layer != "all" and layer not in LAYERS:
            return error_response(
                request,
                "VALIDATION",
                f"layer must be all or one of {', '.join(LAYERS)}.",
                400,
                field="layer",
            )
        plan = get_plan_or_none(plan_id)
        if plan is None:
            return error_response(request, "PLAN_NOT_FOUND", "No plan with this id.", 404)
        body = build_heatmap(str(plan.id), plan.result, weather_provider())
        # Same plan + same forecast hour -> same bytes, so the ETag is cheap and stable.
        etag = f'"{plan.id.hex[:16]}-{body["forecast_as_of"]}-{layer}"'
        headers = {"Cache-Control": "max-age=600", "ETag": etag}
        # GZipMiddleware sends the ETag as weak (W/"…"); If-None-Match uses weak comparison.
        sent = {
            t.strip().removeprefix("W/")
            for t in request.headers.get("If-None-Match", "").split(",")
        }
        if etag in sent or "*" in sent:
            return Response(status=304, headers=headers)
        return Response(select_layers(body, layer), headers=headers)


class GeocodeView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "geocode"

    def get(self, request: Request) -> Response:
        s = GeocodeQuerySerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        try:
            places = geocode.search(
                geocoding_provider(), s.validated_data["q"], s.validated_data["limit"]
            )
        except GeocodeNotFound:
            places = []
        data = [{"label": p.label, "lat": p.lat, "lng": p.lng} for p in places]
        return Response({"data": data}, headers={"Cache-Control": "public, max-age=86400"})


def not_found(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    """JSON 404 for unknown URLs, so no endpoint ever answers with an HTML page."""
    body = {
        "error": {
            "code": "NOT_FOUND",
            "message": "Unknown endpoint.",
            "field": None,
            "request_id": getattr(request, "request_id", None),
            "retryable": False,
        }
    }
    return JsonResponse(body, status=404)
