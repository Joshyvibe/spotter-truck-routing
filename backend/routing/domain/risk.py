"""Risk classification: the brief's threshold table and load rules, encoded as data.

The brief's ranges touch at their edges (rain 0.10–0.25 and 0.25–0.50). They resolve as:
lower bounds are inclusive, and the No Travel column follows the brief exactly
(wind ``>= 55``, rain ``> 1.00``, snow ``> 3.0``). See docs/DESIGN.md §4.3.

| Condition    | Low    | Moderate        | High            | Severe            | No Travel |
|--------------|--------|-----------------|-----------------|-------------------|-----------|
| Wind (mph)   | < 25   | 25 <= w < 35    | 35 <= w < 45    | 45 <= w < 55      | >= 55     |
| Rain (in/hr) | < 0.10 | 0.10 <= r < 0.25| 0.25 <= r < 0.50| 0.50 <= r <= 1.00 | > 1.00    |
| Snow (in/hr) | < 0.5  | 0.5 <= s < 1.0  | 1.0 <= s < 2.0  | 2.0 <= s <= 3.0   | > 3.0     |
"""

from __future__ import annotations

from dataclasses import dataclass

from .types import Assessment, Level, WeatherSample


@dataclass(frozen=True)
class Band:
    """``value < upper`` (or ``<=`` when ``inclusive``) falls in ``level``."""

    level: Level
    upper: float
    inclusive: bool = False

    def contains(self, value: float) -> bool:
        return value <= self.upper if self.inclusive else value < self.upper


# Anything above the last band is NO_TRAVEL.
WIND_BANDS = (
    Band(Level.LOW, 25),
    Band(Level.MODERATE, 35),
    Band(Level.HIGH, 45),
    Band(Level.SEVERE, 55),
)
RAIN_BANDS = (
    Band(Level.LOW, 0.10),
    Band(Level.MODERATE, 0.25),
    Band(Level.HIGH, 0.50),
    Band(Level.SEVERE, 1.00, inclusive=True),
)
SNOW_BANDS = (
    Band(Level.LOW, 0.5),
    Band(Level.MODERATE, 1.0),
    Band(Level.HIGH, 2.0),
    Band(Level.SEVERE, 3.0, inclusive=True),
)


@dataclass(frozen=True)
class LoadRule:
    """Wind in ``[wind_min, wind_max)`` with a load strictly over ``load_over_lb`` is at
    least ``level``. Load rules only raise the wind level, never lower it."""

    wind_min: float
    wind_max: float
    load_over_lb: int
    level: Level


# ">= 55 mph -> No Travel for any load" is already the wind table's last column.
LOAD_RULES = (
    LoadRule(45, 55, 30_000, Level.NO_TRAVEL),
    LoadRule(35, 45, 40_000, Level.SEVERE),
)


def band_level(value: float, bands: tuple[Band, ...]) -> Level:
    for band in bands:
        if band.contains(value):
            return band.level
    return Level.NO_TRAVEL


def wind_level(wind_mph: float, load_lb: int) -> tuple[Level, LoadRule | None]:
    """Return the load-aware wind level and the load rule that raised it, if any."""
    base = band_level(wind_mph, WIND_BANDS)
    for rule in LOAD_RULES:
        if rule.wind_min <= wind_mph < rule.wind_max and load_lb > rule.load_over_lb:
            if rule.level > base:
                return rule.level, rule
            return base, None
    return base, None


def rain_level(rain_in: float) -> Level:
    return band_level(rain_in, RAIN_BANDS)


def snow_level(snow_in: float) -> Level:
    return band_level(snow_in, SNOW_BANDS)


def _label(level: Level) -> str:
    return level.name.replace("_", " ").title()


def assess(weather: WeatherSample, load_lb: int) -> Assessment:
    """Checkpoint level = max(load-aware wind, rain, snow), with the reason that drove it.

    Classification uses sustained wind (the table says "wind"). Gusts are informational.
    """
    if not weather.is_complete:
        return Assessment(None, "unknown", "No forecast available at this ETA")
    assert weather.wind_mph is not None and weather.rain_in is not None
    assert weather.snow_in is not None

    wind, rule = wind_level(weather.wind_mph, load_lb)
    factors: list[tuple[str, Level, str]] = [
        (
            "load" if rule else "wind",
            wind,
            f"Wind {weather.wind_mph:.1f} mph + {load_lb:,} lb load"
            if rule
            else f"Wind {weather.wind_mph:.1f} mph",
        ),
        ("rain", rain_level(weather.rain_in), f"Rain {weather.rain_in:.2f} in/hr"),
        ("snow", snow_level(weather.snow_in), f"Snow {weather.snow_in:.2f} in/hr"),
    ]
    level = max(f[1] for f in factors)
    if level == Level.LOW:
        return Assessment(Level.LOW, "none", "All conditions low")

    worst = [f for f in factors if f[1] == level]
    reason = "; ".join(text for _, _, text in worst) + f" → {_label(level)}"
    return Assessment(level, worst[0][0], reason)
