"""Providers are tested against recorded/documented JSON. No live calls in tests."""

import json
import logging.config
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from routing.domain.types import LatLng
from routing.providers.base import GeocodeNotFound, NoRouteFound, UpstreamUnavailable
from routing.providers.fixture import FixtureRoutingProvider, FixtureWeatherProvider
from routing.providers.openmeteo import OpenMeteoProvider
from routing.providers.tomtom import TomTomProvider

FIX = Path(__file__).parent.parent / "fixtures"
A, B = LatLng(41.8781, -87.6298), LatLng(41.98, -88.13)


def load(name):
    return json.loads((FIX / name).read_text())


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("routing.providers.http.time.sleep", lambda s: None)


def test_tomtom_parses_three_routes_and_sends_truck_params():
    seen = {}

    def handler(req):
        seen.update(dict(req.url.params))
        return httpx.Response(200, json=load("tomtom_route_three.json"))

    routes = TomTomProvider("k", client(handler)).routes(
        A, B, datetime.now(UTC) + timedelta(hours=2), gross_weight_lb=77_000
    )
    assert len(routes) == 3
    assert seen["travelMode"] == "truck"
    assert seen["vehicleWeight"] == str(round(77_000 * 0.45359237))  # kg
    assert seen["maxAlternatives"] == "2"
    r = routes[0]
    assert r.cum_dist_m[0] == 0 and r.cum_dist_m[-1] == pytest.approx(48_000)
    assert r.cum_time_s[-1] == pytest.approx(4200)
    assert all(a <= b for a, b in zip(r.cum_time_s, r.cum_time_s[1:], strict=False))


def test_tomtom_time_profile_follows_instruction_anchors():
    def handler(req):
        return httpx.Response(200, json=load("tomtom_route_three.json"))

    r = TomTomProvider("k", client(handler)).routes(A, B, datetime.now(UTC), 50_000)[0]
    # instruction at pointIndex 3 says 1,800 s; pointIndex 8 says 3,000 s
    assert r.cum_time_s[3] == pytest.approx(1800)
    assert r.cum_time_s[8] == pytest.approx(3000)


def test_tomtom_without_instructions_falls_back_to_average_speed():
    def handler(req):
        return httpx.Response(200, json=load("tomtom_route_three.json"))

    r = TomTomProvider("k", client(handler)).routes(A, B, datetime.now(UTC), 50_000)[1]
    mid = len(r.coords) // 2
    assert r.cum_time_s[mid] / r.duration_s == pytest.approx(r.cum_dist_m[mid] / r.distance_m)


def test_tomtom_past_departure_is_sent_as_now():
    seen = {}

    def handler(req):
        seen.update(dict(req.url.params))
        return httpx.Response(200, json=load("tomtom_route_three.json"))

    TomTomProvider("k", client(handler)).routes(
        A, B, datetime.now(UTC) - timedelta(minutes=30), 50_000
    )
    assert seen["departAt"] == "now"


def test_tomtom_via_request_has_no_alternatives():
    seen = {}

    def handler(req):
        seen["path"] = req.url.path
        seen.update(dict(req.url.params))
        return httpx.Response(200, json=load("tomtom_route_three.json"))

    TomTomProvider("k", client(handler)).routes(
        A, B, datetime.now(UTC), 50_000, via=LatLng(42, -88)
    )
    assert seen["maxAlternatives"] == "0"
    assert seen["path"].count(":") == 2


def test_tomtom_no_route():
    def handler(req):
        return httpx.Response(400, json=load("tomtom_no_route.json"))

    with pytest.raises(NoRouteFound):
        TomTomProvider("k", client(handler)).routes(A, B, datetime.now(UTC), 50_000)


def test_tomtom_5xx_on_alternatives_costs_one_request_and_no_fallback():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(503, json={})

    with pytest.raises(UpstreamUnavailable):
        TomTomProvider("k", client(handler)).routes(A, B, datetime.now(UTC), 50_000)
    assert len(calls) == 1


def test_tomtom_5xx_on_single_route_retries_once():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(503, json={})

    with pytest.raises(UpstreamUnavailable):
        TomTomProvider("k", client(handler)).routes(
            A, B, datetime.now(UTC), 50_000, via=LatLng(42, -88)
        )
    assert len(calls) == 2


def test_tomtom_search():
    def handler(req):
        return httpx.Response(200, json=load("tomtom_search_chicago.json"))

    places = TomTomProvider("k", client(handler)).search("chicago", 5)
    assert places[0].label == "Chicago, IL"


def test_tomtom_search_empty_is_geocode_not_found():
    def handler(req):
        return httpx.Response(200, json={"results": []})

    with pytest.raises(GeocodeNotFound):
        TomTomProvider("k", client(handler)).search("zzzz", 5)


def test_openmeteo_parses_recorded_multi_location_response():
    seen = {}

    def handler(req):
        seen.update(dict(req.url.params))
        return httpx.Response(200, json=load("openmeteo_two_locations.json"))

    series = OpenMeteoProvider(client(handler)).hourly(
        [LatLng(41.88, -87.63), LatLng(61.2, -149.9)]
    )
    assert len(series) == 2
    assert seen["wind_speed_unit"] == "mph" and seen["precipitation_unit"] == "inch"
    raw = load("openmeteo_two_locations.json")[1]["hourly"]
    s = series[1]
    assert s.times == raw["time"]
    # rain rate = large-scale rain + convective showers
    assert s.rain_in == [
        round(r + sh, 3) for r, sh in zip(raw["rain"], raw["showers"], strict=True)
    ]
    assert s.snow_in == raw["snowfall"]


def test_openmeteo_single_location_returns_object():
    one = load("openmeteo_two_locations.json")[0]

    def handler(req):
        return httpx.Response(200, json=one)

    assert len(OpenMeteoProvider(client(handler)).hourly([LatLng(41.88, -87.63)])) == 1


def test_fixture_routes_are_three_bowed_lines():
    routes = FixtureRoutingProvider().routes(A, LatLng(39.74, -104.99), datetime.now(UTC), 50_000)
    assert len(routes) == 3


def test_fixture_weather_replays_the_recording_re_timed():
    """WEATHER_PROVIDER=fixture replays real recorded data (DESIGN §2/§8 "recorded fixture")."""
    import gzip

    from routing.providers.fixture import FIXTURE_PATH, GRID

    with gzip.open(FIXTURE_PATH, "rt") as f:
        rec = json.load(f)
    anchor = datetime(2026, 11, 3, 14, 37, tzinfo=UTC)
    series = FixtureWeatherProvider(anchor).hourly([LatLng(40.4, -100.8)])[0]
    # re-timed: hour 0 = one day before the anchor's hour, hourly, for the recorded length
    assert series.times[0] == int(datetime(2026, 11, 2, 14, tzinfo=UTC).timestamp())
    assert len(series.times) == rec["hours"]
    assert all(b - a == 3600 for a, b in zip(series.times, series.times[1:], strict=False))
    # nearest recorded cell is (41°, -101°): values are the recording's, unchanged
    i = GRID.lats.index(41.0) * len(GRID.lngs) + GRID.lngs.index(-101.0)
    assert series.wind_mph == rec["wind"][i]
    assert series.rain_in == rec["rain"][i]
    assert series.snow_in == rec["snow"][i]


def test_fixture_weather_clamps_points_outside_the_grid():
    far = FixtureWeatherProvider().hourly([LatLng(60.0, -150.0)])[0]  # Alaska -> NW corner
    corner = FixtureWeatherProvider().hourly([LatLng(49.0, -125.0)])[0]
    assert far.wind_mph == corner.wind_mph


def test_tomtom_recorded_real_response_chicago_milwaukee():
    """Recorded live response (key-free): checks the parser on real vendor data."""

    def handler(req):
        return httpx.Response(200, json=load("tomtom_route_chicago_milwaukee.json"))

    routes = TomTomProvider("k", client(handler)).routes(
        A, LatLng(43.0389, -87.9065), datetime.now(UTC), 77_000
    )
    raw = load("tomtom_route_chicago_milwaukee.json")["routes"]
    assert len(routes) == 3
    for r, src in zip(routes, raw, strict=True):
        assert r.distance_m == src["summary"]["lengthInMeters"]
        assert r.cum_time_s[-1] == pytest.approx(src["summary"]["travelTimeInSeconds"])
        assert all(a <= b for a, b in zip(r.cum_time_s, r.cum_time_s[1:], strict=False))
        # Instruction anchors are honoured. Real data can put two instructions on the same
        # point a few seconds apart (back-to-back manoeuvres); the later time wins.
        anchors: dict[int, int] = {}
        for ins in src["guidance"]["instructions"]:
            anchors[ins["pointIndex"]] = ins["travelTimeInSeconds"]
        for i, t in anchors.items():
            if 0 < i < len(r.coords) - 1:
                assert r.cum_time_s[i] == pytest.approx(t)


def test_tomtom_slow_alternatives_fall_back_to_primary_route():
    calls = []

    def handler(req):
        calls.append(req.url.params["maxAlternatives"])
        if req.url.params["maxAlternatives"] == "2":
            raise httpx.ReadTimeout("slow", request=req)
        body = load("tomtom_route_three.json")
        body["routes"] = body["routes"][:1]
        return httpx.Response(200, json=body)

    routes = TomTomProvider("k", client(handler)).routes(A, B, datetime.now(UTC), 50_000)
    assert len(routes) == 1
    # one attempt only for the slow call (a retry would double the wait), then the fallback
    assert calls == ["2", "0"]


def test_api_key_never_reaches_logs(caplog):
    """httpx logs full URLs at INFO and TomTom's key is a query parameter: the project's
    logging config must keep httpx quiet, and our own log lines must not include URLs."""
    from config.settings.base import LOGGING

    logging.config.dictConfig(
        {"version": 1, "disable_existing_loggers": False, "loggers": LOGGING["loggers"]}
    )

    def handler(req):
        return httpx.Response(200, json=load("tomtom_search_chicago.json"))

    with caplog.at_level(logging.INFO):
        # A real httpx.Client with a mock transport still emits httpx's own request log.
        TomTomProvider("SECRET-KEY-123", client(handler)).search("chicago", 1)
    assert "upstream call" in caplog.text
    assert "SECRET-KEY-123" not in caplog.text


def test_tomtom_alternatives_past_deadline_use_primary_route(monkeypatch):
    """A slowly streaming answer never trips the read timeout, so a wall-clock deadline
    decides. Past it the primary route is fetched alone (one extra request)."""
    import threading

    monkeypatch.setattr("routing.providers.tomtom.ALTERNATIVES_DEADLINE_S", 0.1)
    slow = threading.Event()  # time.sleep is patched out in this module; Event.wait is not
    calls = []

    def handler(req):
        calls.append(req.url.params["maxAlternatives"])
        if req.url.params["maxAlternatives"] == "2":
            slow.wait(0.5)  # slower than the deadline, but no timeout error
        body = load("tomtom_route_three.json")
        body["routes"] = body["routes"][:1]
        return httpx.Response(200, json=body)

    routes = TomTomProvider("k", client(handler)).routes(A, B, datetime.now(UTC), 50_000)
    assert len(routes) == 1
    assert sorted(calls) == ["0", "2"]  # the slow call, then exactly one fallback request


def test_tomtom_uses_historic_not_live_traffic():
    seen = {}

    def handler(req):
        seen.update(dict(req.url.params))
        return httpx.Response(200, json=load("tomtom_route_three.json"))

    TomTomProvider("k", client(handler)).routes(A, B, datetime.now(UTC), 50_000)
    assert seen["traffic"] == "false"


def test_tomtom_bad_key_or_quota_is_not_retryable():
    from routing.providers.base import ProviderError

    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(403, json={"detailedError": {"message": "Forbidden"}})

    with pytest.raises(ProviderError) as info:
        TomTomProvider("k", client(handler)).routes(A, B, datetime.now(UTC), 50_000)
    assert not isinstance(info.value, UpstreamUnavailable)  # -> INTERNAL, not a retry prompt
    assert len(calls) == 1


def test_nominatim_spaces_requests_one_second_apart(monkeypatch):
    from routing.providers import nominatim

    waits = []
    monkeypatch.setattr(nominatim.time, "sleep", waits.append)
    monkeypatch.setattr(nominatim, "_last_call", 0.0)

    def handler(req):
        return httpx.Response(
            200, json=[{"display_name": "Chicago", "lat": "41.8", "lon": "-87.6"}]
        )

    geo = nominatim.NominatimGeocoder(client(handler))
    geo.search("chicago", 1)
    geo.search("chicago", 1)
    assert len(waits) == 1 and 0 < waits[0] <= nominatim.MIN_INTERVAL_S


def test_fixture_weather_re_times_on_every_call(monkeypatch):
    """The provider lives for the whole process; its window must follow the clock."""
    from routing.providers import fixture

    provider = FixtureWeatherProvider()  # no anchor, like the running app
    t1 = datetime(2026, 11, 3, 14, 37, tzinfo=UTC)

    class Clock(datetime):
        now_value = t1

        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return cls.now_value

    monkeypatch.setattr(fixture, "datetime", Clock)
    first = provider.hourly([LatLng(40, -100)])[0].times[0]
    Clock.now_value = t1 + timedelta(days=2)
    later = provider.hourly([LatLng(40, -100)])[0].times[0]
    assert later - first == 2 * 24 * 3600
