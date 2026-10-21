"""Heatmap contract: bounded, column-shaped, and scored with the checkpoints' own rules."""

from datetime import UTC, datetime, timedelta

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from routing.domain.risk import assess
from routing.domain.types import LatLng
from routing.domain.weather_at_eta import sample_at
from routing.providers.fixture import FixtureWeatherProvider

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def plan(api):
    depart = (datetime.now(UTC) + timedelta(hours=2)).replace(microsecond=0).isoformat()
    r = api.post(
        "/api/v1/plans",
        {
            "origin": "Salt Lake City, UT",
            "destination": "Chicago, IL",
            "depart_at": depart,
            "load_lb": 42_000,
            "interval_mi": 25,
        },
        format="json",
    )
    assert r.status_code == 201, r.content
    return r.json()


def get(api, plan_id, **params):
    return api.get(f"/api/v1/plans/{plan_id}/heatmap", params)


def test_shape_is_bounded_and_column_shaped(api, plan):
    r = get(api, plan["id"])
    assert r.status_code == 200
    h = r.json()
    n = len(h["points"])
    assert 0 < n <= 400
    assert h["hours"] == 49 and h["start"] == plan["depart_at"]
    for layer in ("risk", "wind", "precip", "snow"):
        assert len(h[layer]) == 49
        assert all(len(row) == n for row in h[layer])
    assert {v for row in h["risk"] for v in row} <= {0, 1, 2, 3, 4, None}
    assert r["Cache-Control"] == "max-age=600"  # DESIGN §6


def test_cells_use_the_same_load_aware_rules_as_checkpoints(api, plan):
    h = get(api, plan["id"]).json()
    start = datetime.fromisoformat(h["start"].replace("Z", "+00:00"))
    weather = FixtureWeatherProvider()
    # Spot-check a spread of (hour, point) cells against the domain function directly.
    for hour in (0, 12, 30, 48):
        for i in range(0, len(h["points"]), max(1, len(h["points"]) // 7)):
            lat, lng = h["points"][i]
            series = weather.hourly([LatLng(lat, lng)])[0]
            level = assess(sample_at(series, start + timedelta(hours=hour)), 42_000).level
            assert h["risk"][hour][i] == (None if level is None else int(level))


def test_hours_come_from_different_forecast_times(api, plan):
    wind = get(api, plan["id"]).json()["wind"]
    # The recorded weather changes over two days, so the slider shows different fields.
    assert wind[0] != wind[24] != wind[48]


def test_single_layer_and_validation(api, plan):
    only = get(api, plan["id"], layer="risk").json()
    assert "risk" in only and "wind" not in only and "points" in only
    r = get(api, plan["id"], layer="pressure")
    assert r.status_code == 400 and r.json()["error"]["field"] == "layer"


def test_unknown_plan(api):
    r = get(api, "00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404 and r.json()["error"]["code"] == "PLAN_NOT_FOUND"


def test_etag_and_cache(api, plan, monkeypatch):
    first = get(api, plan["id"])
    calls = []
    monkeypatch.setattr(
        FixtureWeatherProvider, "hourly", lambda self, pts: calls.append(len(pts)) or []
    )
    again = api.get(f"/api/v1/plans/{plan['id']}/heatmap", HTTP_IF_NONE_MATCH=first["ETag"])
    assert again.status_code == 304
    assert calls == []  # served from the heatmap cache, no weather lookups


def test_etag_revalidates_through_gzip(api, plan):
    # GZipMiddleware turns the ETag weak (W/"…"); sending it back must still give 304.
    first = api.get(f"/api/v1/plans/{plan['id']}/heatmap", HTTP_ACCEPT_ENCODING="gzip")
    assert first["ETag"].startswith('W/"')
    again = api.get(
        f"/api/v1/plans/{plan['id']}/heatmap",
        HTTP_ACCEPT_ENCODING="gzip",
        HTTP_IF_NONE_MATCH=first["ETag"],
    )
    assert again.status_code == 304
