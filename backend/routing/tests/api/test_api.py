"""API contract tests with the offline fixture providers (no live calls)."""

from datetime import UTC, datetime, timedelta

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from routing.models import TripPlan

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


@pytest.fixture
def api():
    return APIClient()


def depart(hours=2):
    return (datetime.now(UTC) + timedelta(hours=hours)).replace(microsecond=0).isoformat()


def body(**over):
    b = {
        "origin": "Chicago, IL",
        "destination": "Denver, CO",
        "depart_at": depart(),
        "load_lb": 42_000,
        "interval_mi": 25,
    }
    b.update(over)
    return b


def post(api, **over):
    return api.post("/api/v1/plans", body(**over), format="json")


def assert_error(resp, status, code, field=None):
    assert resp.status_code == status, resp.content
    err = resp.json()["error"]
    assert err["code"] == code
    assert err["field"] == field
    assert err["request_id"] == resp["X-Request-ID"]
    assert set(err) == {"code", "message", "field", "request_id", "retryable"}
    return err


def test_health(api):
    r = api.get("/api/v1/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_create_plan_contract(api):
    r = post(api)
    assert r.status_code == 201, r.content
    p = r.json()
    assert r["Location"] == f"/api/v1/plans/{p['id']}"
    assert {
        "id",
        "created_at",
        "forecast_as_of",
        "origin",
        "destination",
        "depart_at",
        "load_lb",
        "interval_mi",
        "recommended_route_id",
        "recommendation_reason",
        "all_routes_unsafe",
        "warnings",
        "routes",
    } <= set(p)
    assert len(p["routes"]) == 3
    route = p["routes"][0]
    assert route["is_recommended"] and route["id"] == p["recommended_route_id"]
    assert {
        "id",
        "label",
        "rank",
        "distance_mi",
        "duration_s",
        "arrive_at",
        "geometry",
        "summary",
        "risk_segments",
        "checkpoints",
    } <= set(route)
    cp = route["checkpoints"][0]
    assert {
        "mile",
        "lat",
        "lng",
        "eta",
        "wind_mph",
        "gust_mph",
        "rain_in",
        "snow_in",
        "level",
        "driver",
        "reason",
        "segment_mi",
        "kind",
    } <= set(cp)
    assert TripPlan.objects.count() == 1


def test_accepts_autocomplete_objects(api):
    r = post(
        api,
        origin={"lat": 41.8781, "lng": -87.6298, "label": "Chicago, IL"},
        destination={"lat": 39.7392, "lng": -104.9903, "label": "Denver, CO"},
    )
    assert r.status_code == 201
    assert r.json()["origin"]["label"] == "Chicago, IL"


def test_get_saved_plan_returns_same_body(api):
    created = post(api).json()
    r = api.get(f"/api/v1/plans/{created['id']}")
    assert r.status_code == 200
    assert r.json() == created
    assert r["Cache-Control"] == "private, max-age=600"


@pytest.mark.parametrize("plan_id", ["00000000-0000-0000-0000-000000000000", "not-a-uuid"])
def test_unknown_plan_is_404_envelope(api, plan_id):
    assert_error(api.get(f"/api/v1/plans/{plan_id}"), 404, "PLAN_NOT_FOUND")


@pytest.mark.parametrize(
    ("over", "field"),
    [
        ({"load_lb": 0}, "load_lb"),
        ({"load_lb": 80_001}, "load_lb"),
        ({"interval_mi": 20}, "interval_mi"),
        ({"depart_at": "2026-10-21T08:00:00"}, "depart_at"),  # naive: no offset
        ({"depart_at": "tomorrow"}, "depart_at"),
        ({"depart_at": depart(hours=-2)}, "depart_at"),
        ({"depart_at": depart(hours=24 * 7 + 1)}, "depart_at"),
        ({"origin": ""}, "origin"),
        ({"origin": {"lat": 95, "lng": 0}}, "origin"),
        ({"destination": 42}, "destination"),
    ],
)
def test_validation_errors(api, over, field):
    assert_error(post(api, **over), 400, "VALIDATION", field)


def test_departure_up_to_one_hour_in_past_is_allowed(api):
    assert post(api, depart_at=depart(hours=-0.5)).status_code == 201


def test_missing_fields(api):
    r = api.post("/api/v1/plans", {}, format="json")
    assert_error(r, 400, "VALIDATION", "origin")


def test_same_origin_and_destination(api):
    assert_error(post(api, destination="Chicago, IL"), 400, "VALIDATION", "destination")


def test_geocode_miss_names_the_field(api):
    assert_error(post(api, destination="Atlantis"), 422, "GEOCODE_NOT_FOUND", "destination")


def test_no_route(api, monkeypatch):
    from routing.providers.base import NoRouteFound
    from routing.providers.fixture import FixtureRoutingProvider

    def boom(*a, **k):
        raise NoRouteFound("x")

    monkeypatch.setattr(FixtureRoutingProvider, "routes", boom)
    assert_error(post(api), 422, "NO_ROUTE")


def test_upstream_down_is_retryable_502(api, monkeypatch):
    from routing.providers.base import UpstreamUnavailable
    from routing.providers.fixture import FixtureWeatherProvider

    def boom(*a, **k):
        raise UpstreamUnavailable("open-meteo 503")

    monkeypatch.setattr(FixtureWeatherProvider, "hourly", boom)
    err = assert_error(post(api), 502, "UPSTREAM_UNAVAILABLE")
    assert err["retryable"] is True


def test_malformed_json(api):
    r = api.post("/api/v1/plans", "{not json", content_type="application/json")
    assert_error(r, 400, "VALIDATION")


def test_unknown_endpoint_is_json(api):
    r = api.get("/api/v1/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_request_id_is_echoed(api):
    r = api.get("/api/v1/health", HTTP_X_REQUEST_ID="req_abc123")
    assert r["X-Request-ID"] == "req_abc123"


def test_geocode(api):
    r = api.get("/api/v1/geocode", {"q": "chic"})
    assert r.status_code == 200
    assert r.json()["data"][0]["label"].startswith("Chicago")
    assert r["Cache-Control"] == "public, max-age=86400"


def test_geocode_short_query(api):
    assert_error(api.get("/api/v1/geocode", {"q": "ch"}), 400, "VALIDATION", "q")


def test_geocode_no_results_is_empty_list(api):
    assert api.get("/api/v1/geocode", {"q": "atlantis"}).json() == {"data": []}


def test_rate_limit_sends_retry_after(api):
    from rest_framework.settings import api_settings
    from rest_framework.throttling import SimpleRateThrottle

    rates = {**api_settings.DEFAULT_THROTTLE_RATES, "geocode": "2/min"}
    original = SimpleRateThrottle.THROTTLE_RATES
    SimpleRateThrottle.THROTTLE_RATES = rates
    try:
        for _ in range(2):
            api.get("/api/v1/geocode", {"q": "chicago"})
        r = api.get("/api/v1/geocode", {"q": "chicago"})
    finally:
        SimpleRateThrottle.THROTTLE_RATES = original
    err = assert_error(r, 429, "RATE_LIMITED")
    assert err["retryable"] is True
    assert int(r["Retry-After"]) > 0


def test_request_body_over_16_kb_is_rejected(api):
    big = '{"origin": "' + "a" * 20_000 + '"}'
    r = api.post("/api/v1/plans", big, content_type="application/json")
    err = assert_error(r, 400, "VALIDATION")
    assert "16 KB" in err["message"]
