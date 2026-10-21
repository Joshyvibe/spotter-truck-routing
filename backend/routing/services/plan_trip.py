"""Orchestration for ``POST /plans`` (docs/DESIGN.md §3). I/O lives here; logic in domain/."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import polyline
from django.conf import settings

from routing.domain.checkpoints import place_checkpoints
from routing.domain.geometry import simplify, slice_by_distance
from routing.domain.ranking import Recommendation, ScoredSegment, fmt_miles, recommend, score_route
from routing.domain.risk import assess
from routing.domain.segments import merge_runs
from routing.domain.types import (
    METERS_PER_MILE,
    Assessment,
    CheckpointPosition,
    LatLng,
    Level,
    RawRoute,
    WeatherSample,
    level_name,
)
from routing.domain.weather_at_eta import sample_at
from routing.providers.base import Place, RoutingProvider, WeatherProvider

from .routes import TARGET_ROUTES, get_routes
from .weather import forecast_hour, series_for_cells, snap

log = logging.getLogger(__name__)

LABELS = "ABC"
DISPLAY_TOLERANCE_M = 25.0


@dataclass(frozen=True)
class PlanInputs:
    origin: Place
    destination: Place
    depart_at: datetime  # aware
    load_lb: int
    interval_mi: int


@dataclass(frozen=True)
class EvaluatedRoute:
    id: str
    raw: RawRoute
    checkpoints: list[tuple[CheckpointPosition, WeatherSample, Assessment]]


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _encode(coords: list[LatLng]) -> str:
    return str(polyline.encode([(c.lat, c.lng) for c in coords], 5))


def gross_weight_lb(load_lb: int) -> int:
    """TomTom routes on gross vehicle weight; the brief's risk rules use load (R7)."""
    return load_lb + int(settings.TRUCK_TARE_LB)


def plan_trip(
    inputs: PlanInputs, routing: RoutingProvider, weather: WeatherProvider
) -> dict[str, Any]:
    started = time.perf_counter()
    origin = LatLng(inputs.origin.lat, inputs.origin.lng)
    dest = LatLng(inputs.destination.lat, inputs.destination.lng)
    raws = get_routes(routing, origin, dest, inputs.depart_at, gross_weight_lb(inputs.load_lb))

    # Same interval on every route, so the comparison is fair.
    placed = {
        LABELS[i]: place_checkpoints(r, inputs.interval_mi, inputs.depart_at)
        for i, r in enumerate(raws)
    }
    issued = forecast_hour()
    series = series_for_cells(
        weather, [snap(c.point) for cps in placed.values() for c in cps], issued
    )

    evaluated: list[EvaluatedRoute] = []
    for i, raw in enumerate(raws):
        rid = LABELS[i]
        rows = []
        for cp in placed[rid]:
            sample = sample_at(series[snap(cp.point)], cp.eta)
            rows.append((cp, sample, assess(sample, inputs.load_lb)))
        evaluated.append(EvaluatedRoute(rid, raw, rows))

    scores = [
        score_route(
            e.id,
            f"Route {e.id}",
            e.raw.duration_s,
            [ScoredSegment(a.level, cp.segment_mi) for cp, _, a in e.checkpoints],
        )
        for e in evaluated
    ]
    rec = recommend(scores)
    result = _serialize(inputs, evaluated, rec, issued)
    log.info(
        "plan computed",
        extra={
            "routes": len(raws),
            "ms": round((time.perf_counter() - started) * 1000),
            "recommended": rec.best.route_id,
        },
    )
    return result


def _serialize(
    inputs: PlanInputs, evaluated: list[EvaluatedRoute], rec: Recommendation, issued: str
) -> dict[str, Any]:
    by_id = {e.id: e for e in evaluated}
    routes = []
    warnings: list[str] = []
    if len(evaluated) < TARGET_ROUTES:
        warnings.append(
            f"Only {len(evaluated)} distinct truck route(s) exist for this trip; "
            "showing what the routing provider found."
        )
    for rank, score in enumerate(rec.ranked, start=1):
        e = by_id[score.route_id]
        raw = e.raw
        summary = {
            "no_travel_mi": round(score.no_travel_mi, 1),
            "severe_mi": round(score.severe_mi, 1),
            "high_mi": round(score.high_mi, 1),
            "moderate_mi": round(score.miles_by_level.get(Level.MODERATE, 0.0), 1),
            "low_mi": round(score.miles_by_level.get(Level.LOW, 0.0), 1),
            "unknown_mi": round(score.unknown_mi, 1),
            "avg_risk": None if score.avg_risk is None else round(score.avg_risk, 2),
        }
        if score.no_travel_mi > 0:
            warnings.append(
                f"{score.label} has {fmt_miles(score.no_travel_mi)} miles of No Travel conditions."
            )
        if score.unknown_mi > 0:
            warnings.append(
                f"{score.label} has {fmt_miles(score.unknown_mi)} miles with no forecast "
                "(shown grey)."
            )
        runs = merge_runs(
            [(cp.segment_start_mi, cp.segment_end_mi, a.level) for cp, _, a in e.checkpoints]
        )
        risk_segments = [
            {
                "from_mi": round(run.from_mi, 2),
                "to_mi": round(run.to_mi, 2),
                "level": level_name(run.level),
                "geometry": _encode(
                    simplify(
                        slice_by_distance(
                            raw.coords,
                            raw.cum_dist_m,
                            run.from_mi * METERS_PER_MILE,
                            run.to_mi * METERS_PER_MILE,
                        ),
                        DISPLAY_TOLERANCE_M,
                    )
                ),
            }
            for run in runs
        ]
        arrive_at = inputs.depart_at.timestamp() + raw.duration_s
        routes.append(
            {
                "id": e.id,
                "label": score.label,
                "rank": rank,
                "is_recommended": rank == 1,
                "distance_mi": round(raw.distance_m / METERS_PER_MILE, 1),
                "duration_s": round(raw.duration_s),
                "arrive_at": _iso(datetime.fromtimestamp(arrive_at, UTC)),
                "geometry": _encode(simplify(raw.coords, DISPLAY_TOLERANCE_M)),
                "summary": summary,
                "risk_segments": risk_segments,
                "checkpoints": [_checkpoint(cp, s, a) for cp, s, a in e.checkpoints],
            }
        )
    return {
        "forecast_as_of": _iso(datetime.strptime(issued, "%Y%m%d%H").replace(tzinfo=UTC)),
        "origin": _place(inputs.origin),
        "destination": _place(inputs.destination),
        "depart_at": _iso(inputs.depart_at),
        "load_lb": inputs.load_lb,
        "interval_mi": inputs.interval_mi,
        "recommended_route_id": rec.best.route_id,
        "recommendation_reason": rec.reason,
        "all_routes_unsafe": rec.all_routes_unsafe,
        "warnings": warnings,
        "routes": routes,
    }


def _place(p: Place) -> dict[str, Any]:
    return {"lat": round(p.lat, 6), "lng": round(p.lng, 6), "label": p.label}


def _r(v: float | None, nd: int) -> float | None:
    return None if v is None else round(v, nd)


def _checkpoint(cp: CheckpointPosition, s: WeatherSample, a: Assessment) -> dict[str, Any]:
    return {
        "index": cp.index,
        "kind": cp.kind,
        "mile": round(cp.mile, 1),
        "lat": round(cp.point.lat, 5),
        "lng": round(cp.point.lng, 5),
        "eta": _iso(cp.eta),
        "wind_mph": _r(s.wind_mph, 1),
        "gust_mph": _r(s.gust_mph, 1),
        "rain_in": _r(s.rain_in, 2),
        "snow_in": _r(s.snow_in, 2),
        "level": level_name(a.level),
        "driver": a.driver,
        "reason": a.reason,
        "segment_mi": round(cp.segment_mi, 2),
    }
