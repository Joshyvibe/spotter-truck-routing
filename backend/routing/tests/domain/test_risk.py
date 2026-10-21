"""Every boundary of the brief's table and load rules. The table here *is* the spec."""

import pytest

from routing.domain.risk import assess, rain_level, snow_level, wind_level
from routing.domain.types import Level, WeatherSample

L, M, H, S, NT = Level.LOW, Level.MODERATE, Level.HIGH, Level.SEVERE, Level.NO_TRAVEL


def wx(wind=0.0, rain=0.0, snow=0.0, gust=None):
    return WeatherSample(wind_mph=wind, gust_mph=gust, rain_in=rain, snow_in=snow)


@pytest.mark.parametrize(
    ("mph", "expected"),
    [
        (0, L),
        (24.99, L),
        (25, M),
        (34.99, M),
        (35, H),
        (44.99, H),
        (45, S),
        (54.99, S),
        (55, NT),
        (80, NT),
    ],
)
def test_wind_table_light_load(mph, expected):
    assert wind_level(mph, load_lb=10_000)[0] == expected


@pytest.mark.parametrize(
    ("rain", "expected"),
    [
        (0, L),
        (0.0999, L),
        (0.10, M),
        (0.2499, M),
        (0.25, H),
        (0.4999, H),
        (0.50, S),
        (1.00, S),
        (1.0001, NT),
        (2.5, NT),
    ],
)
def test_rain_table(rain, expected):
    assert rain_level(rain) == expected


@pytest.mark.parametrize(
    ("snow", "expected"),
    [
        (0, L),
        (0.499, L),
        (0.5, M),
        (0.999, M),
        (1.0, H),
        (1.999, H),
        (2.0, S),
        (3.0, S),
        (3.01, NT),
        (6, NT),
    ],
)
def test_snow_table(snow, expected):
    assert snow_level(snow) == expected


@pytest.mark.parametrize(
    ("mph", "load", "expected"),
    [
        # >= 55 mph -> No Travel for any load
        (55, 1, NT),
        (55, 80_000, NT),
        # 45–54 mph + > 30,000 lb -> No Travel
        (45, 30_000, S),
        (45, 30_001, NT),
        (54.99, 30_001, NT),
        (54.99, 30_000, S),
        # 35–44 mph + > 40,000 lb -> Severe
        (35, 40_000, H),
        (35, 40_001, S),
        (44.99, 40_001, S),
        (44.99, 40_000, H),
        # just outside the rule's wind range: no effect
        (34.99, 80_000, M),
        # 35–44 with 30,001–40,000 lb stays High (only the 45–54 rule uses 30,000)
        (40, 35_000, H),
    ],
)
def test_load_rules(mph, load, expected):
    assert wind_level(mph, load)[0] == expected


def test_load_rule_is_reported_as_driver():
    a = assess(wx(wind=47), load_lb=42_000)
    assert a.level == NT
    assert a.driver == "load"
    assert a.reason == "Wind 47.0 mph + 42,000 lb load → No Travel"


def test_checkpoint_is_max_of_factors():
    a = assess(wx(wind=26, rain=0.3, snow=0.6), load_lb=10_000)
    assert a.level == H
    assert a.driver == "rain"
    assert a.reason == "Rain 0.30 in/hr → High"


def test_ties_list_every_worst_factor():
    a = assess(wx(wind=36, rain=0.3), load_lb=10_000)
    assert a.level == H
    assert a.reason == "Wind 36.0 mph; Rain 0.30 in/hr → High"


def test_all_low():
    a = assess(wx(wind=10, rain=0.01), load_lb=80_000)
    assert (a.level, a.driver, a.reason) == (L, "none", "All conditions low")


def test_gusts_are_not_scored():
    assert assess(wx(wind=10, gust=70), load_lb=50_000).level == L


def test_missing_forecast_is_unknown_never_low():
    a = assess(WeatherSample(None, None, None, None), load_lb=10_000)
    assert a.level is None
    assert a.driver == "unknown"


@pytest.mark.parametrize(
    ("mph", "text"), [(34.7, "Wind 34.7 mph → Moderate"), (54.6, "Wind 54.6 mph → Severe")]
)
def test_reason_never_reads_across_a_band_edge(mph, text):
    # Rounded to whole mph these would read "35 mph → Moderate" / "55 mph → Severe".
    assert assess(wx(wind=mph), load_lb=10_000).reason == text
