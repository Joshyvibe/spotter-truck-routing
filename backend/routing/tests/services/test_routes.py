"""The "fewer than 3 routes" fill path (docs/DESIGN.md §2 and §9).

TomTom can return fewer than 3 routes on short or direct trips. We then ask again through a
via point either side of the midpoint, drop near-duplicates (> 90% shared geometry), and never
invent a route: if there are still fewer than 3, the plan shows what exists plus a warning.
"""

from datetime import UTC, datetime, timedelta

import pytest
from django.core.cache import cache

from routing.domain.types import LatLng
from routing.providers.base import NoRouteFound, Place
from routing.providers.fixture import FixtureRoutingProvider, FixtureWeatherProvider, _bowed_route
from routing.services.plan_trip import PlanInputs, plan_trip
from routing.services.routes import get_routes

A, B = LatLng(41.88, -87.63), LatLng(39.74, -104.99)
DEPART = datetime(2026, 10, 21, 13, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


class FakeRouting:
    """Primary call returns ``primary`` routes; each via call returns the next ``via`` item."""

    def __init__(self, primary, via):
        self.primary = primary
        self.via = list(via)
        self.calls = []

    def routes(self, origin, dest, depart_at, gross_weight_lb, via=None):
        self.calls.append(via)
        if via is None:
            return self.primary
        item = self.via.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def bowed(bow):
    return _bowed_route(A, B, bow)


def test_three_routes_from_provider_need_no_via_calls():
    p = FakeRouting([bowed(0), bowed(0.12), bowed(-0.12)], via=[])
    assert len(get_routes(p, A, B, DEPART, 77_000)) == 3
    assert p.calls == [None]


def test_one_route_is_filled_to_three_through_via_points():
    p = FakeRouting([bowed(0)], via=[[bowed(0.15)], [bowed(-0.15)]])
    routes = get_routes(p, A, B, DEPART, 77_000)
    assert len(routes) == 3
    assert p.calls[0] is None and all(v is not None for v in p.calls[1:])
    assert len(p.calls) == 3  # primary + 2 via calls, no more


def test_fill_stops_as_soon_as_there_are_three():
    p = FakeRouting([bowed(0), bowed(0.12)], via=[[bowed(-0.12)], [bowed(0.3)]])
    assert len(get_routes(p, A, B, DEPART, 77_000)) == 3
    assert len(p.calls) == 2  # the second via point is never requested


def test_near_duplicates_are_dropped_and_no_route_is_invented():
    # Both via routes collapse onto the primary line (> 90% shared geometry).
    p = FakeRouting([bowed(0)], via=[[bowed(0.0005)], [bowed(-0.0005)]])
    routes = get_routes(p, A, B, DEPART, 77_000)
    assert len(routes) == 1


def test_a_failing_via_call_is_skipped():
    p = FakeRouting([bowed(0)], via=[NoRouteFound("x"), [bowed(-0.15)]])
    assert len(get_routes(p, A, B, DEPART, 77_000)) == 2


def test_routes_are_cached_for_the_same_trip():
    p = FakeRouting([bowed(0), bowed(0.12), bowed(-0.12)], via=[])
    get_routes(p, A, B, DEPART, 77_000)
    get_routes(p, A, B, DEPART + timedelta(minutes=5), 77_000)  # same 15-minute slot
    assert p.calls == [None]


def test_plan_warns_when_fewer_than_three_routes_exist(monkeypatch):
    def one_route(self, origin, dest, depart_at, gross_weight_lb, via=None):
        return [_bowed_route(origin, dest, 0.0)]  # via calls return the same line again

    monkeypatch.setattr(FixtureRoutingProvider, "routes", one_route)
    plan = plan_trip(
        PlanInputs(
            Place("Chicago, IL", A.lat, A.lng),
            Place("Denver, CO", B.lat, B.lng),
            datetime.now(UTC) + timedelta(hours=2),
            42_000,
            25,
        ),
        FixtureRoutingProvider(),
        FixtureWeatherProvider(),
    )
    assert len(plan["routes"]) == 1
    assert plan["warnings"][0].startswith("Only 1 distinct truck route(s) exist")
    assert plan["recommendation_reason"] == "Route A is the only route available."


def test_a_transient_via_failure_is_not_cached():
    from routing.providers.base import UpstreamUnavailable

    p = FakeRouting([bowed(0)], via=[UpstreamUnavailable("503"), [bowed(-0.15)]])
    assert len(get_routes(p, A, B, DEPART, 77_000)) == 2
    p.via = [[bowed(0.15)], [bowed(-0.15)]]  # upstream recovered
    assert len(get_routes(p, A, B, DEPART, 77_000)) == 3  # asked again, not served from cache


def test_geocode_cache_is_per_provider():
    from routing.providers.base import Place
    from routing.services.geocode import search

    class One:
        def search(self, q, limit):
            return [Place("from one", 1, 1)]

    class Two:
        def search(self, q, limit):
            return [Place("from two", 2, 2)]

    assert search(One(), "springfield")[0].label == "from one"
    assert search(Two(), "springfield")[0].label == "from two"
