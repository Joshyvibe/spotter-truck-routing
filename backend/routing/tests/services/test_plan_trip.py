from datetime import UTC, datetime, timedelta

import polyline
import pytest
from django.core.cache import cache

from routing.domain.types import LatLng
from routing.providers.base import Place
from routing.providers.fixture import FixtureRoutingProvider, FixtureWeatherProvider
from routing.services.plan_trip import PlanInputs, gross_weight_lb, plan_trip
from routing.services.routes import via_points
from routing.services.weather import series_for_cells, snap

CHI = Place("Chicago, IL", 41.8781, -87.6298)
DEN = Place("Denver, CO", 39.7392, -104.9903)


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


def make(interval=25, load=42_000):
    depart = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)
    return plan_trip(
        PlanInputs(CHI, DEN, depart, load, interval),
        FixtureRoutingProvider(),
        FixtureWeatherProvider(),
    )


@pytest.mark.parametrize("interval", [10, 25, 50])
def test_three_routes_same_interval_and_miles_add_up(interval):
    plan = make(interval)
    assert len(plan["routes"]) == 3
    for r in plan["routes"]:
        miles = [c["mile"] for c in r["checkpoints"]]
        assert miles[0] == 0 and miles[-1] == pytest.approx(r["distance_mi"], abs=0.05)
        assert all(b - a <= interval + 1e-6 for a, b in zip(miles, miles[1:], strict=False))
        assert sum(c["segment_mi"] for c in r["checkpoints"]) == pytest.approx(
            r["distance_mi"], abs=0.1
        )
        s = r["summary"]
        total = sum(
            s[k]
            for k in ("no_travel_mi", "severe_mi", "high_mi", "moderate_mi", "low_mi", "unknown_mi")
        )
        assert total == pytest.approx(r["distance_mi"], abs=0.5)


def test_recommended_route_is_rank_one_and_explained():
    plan = make()
    first = plan["routes"][0]
    assert first["rank"] == 1 and first["is_recommended"]
    assert first["id"] == plan["recommended_route_id"]
    assert plan["recommendation_reason"].startswith(f"{first['label']} recommended")
    assert [r["rank"] for r in plan["routes"]] == [1, 2, 3]


def test_risk_segments_cover_the_route_and_decode():
    for r in make()["routes"]:
        segs = r["risk_segments"]
        assert segs[0]["from_mi"] == 0
        assert segs[-1]["to_mi"] == pytest.approx(r["distance_mi"], abs=0.05)
        assert all(len(polyline.decode(s["geometry"])) >= 2 for s in segs)


def test_timestamps_are_utc_z_without_microseconds():
    plan = make()
    cp = plan["routes"][0]["checkpoints"][3]
    assert cp["eta"].endswith("Z") and "." not in cp["eta"]


def test_gross_weight_adds_tare():
    assert gross_weight_lb(42_000) == 77_000


def test_weather_cells_are_deduped_and_cached():
    calls = []

    class CountingWeather(FixtureWeatherProvider):
        def hourly(self, points):
            calls.append(len(points))
            return super().hourly(points)

    w = CountingWeather()
    route = FixtureRoutingProvider().routes(
        LatLng(CHI.lat, CHI.lng), LatLng(DEN.lat, DEN.lng), datetime.now(UTC), 1
    )[0]
    cells = [snap(p) for p in route.coords] * 2
    series_for_cells(w, cells, "2026102012")
    first = sum(calls)
    series_for_cells(w, cells, "2026102012")
    assert first == len(set(cells))
    assert sum(calls) == first  # second call is fully cached


def test_via_points_sit_either_side_of_the_route():
    r = FixtureRoutingProvider().routes(LatLng(40, -100), LatLng(40, -90), datetime.now(UTC), 1)[0]
    north, south = via_points(r)
    assert north.lat > 40 > south.lat
