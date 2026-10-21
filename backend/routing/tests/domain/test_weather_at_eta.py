from datetime import UTC, datetime

import pytest

from routing.domain.types import HourlySeries
from routing.domain.weather_at_eta import sample_at

T0 = int(datetime(2026, 10, 21, 13, tzinfo=UTC).timestamp())


def series():
    times = [T0 + h * 3600 for h in range(4)]  # 13:00, 14:00, 15:00, 16:00
    return HourlySeries(
        times=times,
        wind_mph=[10.0, 20.0, 40.0, 30.0],
        gust_mph=[15.0, 25.0, 45.0, 35.0],
        rain_in=[0.00, 0.05, 0.30, 0.10],  # labelled at the END of the hour
        snow_in=[0.0, 0.0, 0.6, 0.0],
    )


def at(h, m=0):
    return datetime(2026, 10, 21, h, m, tzinfo=UTC)


def test_wind_is_interpolated():
    s = sample_at(series(), at(14, 15))
    assert s.wind_mph == pytest.approx(25.0)
    assert s.gust_mph == pytest.approx(30.0)


def test_precip_uses_hour_ending_value_covering_eta():
    # ETA 14:20 is inside 14:00–15:00, which Open-Meteo labels 15:00.
    s = sample_at(series(), at(14, 20))
    assert s.rain_in == 0.30
    assert s.snow_in == 0.6


def test_eta_exactly_on_the_hour_uses_the_hour_being_driven():
    # Departing 13:00: the truck drives 13:00–14:00, labelled 14:00 (not 12:00–13:00).
    s = sample_at(series(), at(13))
    assert s.rain_in == 0.05
    assert s.wind_mph == 10.0


def test_outside_forecast_is_none():
    s = sample_at(series(), at(16, 30))
    assert s.wind_mph is None
    assert s.rain_in is None
    assert not s.is_complete
