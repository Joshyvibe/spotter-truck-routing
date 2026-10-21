from datetime import UTC, datetime

import pytest

from routing.domain.geometry import cumulative_distances
from routing.domain.types import METERS_PER_MILE, LatLng, RawRoute


def straight_route(miles: float, mph: float = 60.0, n: int = 200) -> RawRoute:
    """A due-north route of ``miles`` at constant speed, with distances scaled exactly."""
    lat_span = miles * METERS_PER_MILE / 111_195.0
    coords = [LatLng(40.0 + lat_span * i / (n - 1), -100.0) for i in range(n)]
    cum = cumulative_distances(coords)
    total = miles * METERS_PER_MILE
    cum = [d * total / cum[-1] for d in cum]
    speed = mph * METERS_PER_MILE / 3600
    return RawRoute(coords, cum, [d / speed for d in cum], total, total / speed)


@pytest.fixture
def depart():
    return datetime(2026, 10, 21, 13, 0, tzinfo=UTC)
