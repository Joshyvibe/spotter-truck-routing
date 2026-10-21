"""Route scoring and the recommendation (docs/DESIGN.md §4.4).

The brief's preference order, applied lexicographically (a later rule only breaks ties):
  0. (gate, ours) no No Travel miles — No Travel is worse than Severe, so it sits above rule 1
  0b. (ours, TECHNICAL_DESIGN §9 D7) fewest miles without a forecast — UNKNOWN is never
      treated as Low (DESIGN §4.2), so a route we cannot check never beats one we can
  1. fewest Severe miles
  2. fewest High miles
  3. lowest average risk (distance-weighted level index 0–4 over miles with a forecast)
  4. shortest travel time
Miles are rounded to 0.1 and average risk to 0.01 so float noise never picks the winner.
Full ties keep the provider's order (Route A first).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from .types import Level

# Display/label order of the per-level mile buckets.
SUMMARY_LEVELS = (Level.NO_TRAVEL, Level.SEVERE, Level.HIGH, Level.MODERATE, Level.LOW)


@dataclass(frozen=True)
class ScoredSegment:
    level: Level | None  # None = UNKNOWN
    miles: float


@dataclass(frozen=True)
class RouteScore:
    route_id: str
    label: str
    duration_s: float
    miles_by_level: dict[Level, float] = field(default_factory=dict)
    unknown_mi: float = 0.0

    @property
    def no_travel_mi(self) -> float:
        return self.miles_by_level.get(Level.NO_TRAVEL, 0.0)

    @property
    def severe_mi(self) -> float:
        return self.miles_by_level.get(Level.SEVERE, 0.0)

    @property
    def high_mi(self) -> float:
        return self.miles_by_level.get(Level.HIGH, 0.0)

    @property
    def known_mi(self) -> float:
        return sum(self.miles_by_level.values())

    @property
    def avg_risk(self) -> float | None:
        known = self.known_mi
        if known <= 0:
            return None
        return sum(int(lvl) * mi for lvl, mi in self.miles_by_level.items()) / known

    def sort_key(self) -> tuple[bool, float, float, float, float, float, float]:
        avg = self.avg_risk
        return (
            self.no_travel_mi > 0,
            round(self.no_travel_mi, 1),
            round(self.unknown_mi, 1),
            round(self.severe_mi, 1),
            round(self.high_mi, 1),
            round(avg, 2) if avg is not None else float("inf"),
            self.duration_s,
        )


def score_route(
    route_id: str, label: str, duration_s: float, segments: Sequence[ScoredSegment]
) -> RouteScore:
    by_level: dict[Level, float] = {lvl: 0.0 for lvl in Level}
    unknown = 0.0
    for seg in segments:
        if seg.level is None:
            unknown += seg.miles
        else:
            by_level[seg.level] += seg.miles
    return RouteScore(route_id, label, duration_s, by_level, unknown)


@dataclass(frozen=True)
class Recommendation:
    ranked: list[RouteScore]  # best first
    reason: str
    all_routes_unsafe: bool

    @property
    def best(self) -> RouteScore:
        return self.ranked[0]


def format_duration(seconds: float) -> str:
    minutes = round(seconds / 60)
    return f"{minutes // 60}h {minutes % 60:02d}m"


def fmt_miles(mi: float) -> str:
    # A real but tiny stretch (e.g. 0.03 mi) must not read as "0": the gate counts it.
    return "<0.1" if 0 < mi < 0.05 else f"{round(mi, 1):g}"


def _fmt_avg(s: RouteScore) -> str:
    return "n/a" if s.avg_risk is None else f"{s.avg_risk:.2f}"


def _fmt_time(s: RouteScore) -> str:
    return format_duration(s.duration_s)


def _fmt_time_s(s: RouteScore) -> str:
    """Seconds too, for when routes differ by less than a minute."""
    total = round(s.duration_s)
    return f"{total // 3600}h {total % 3600 // 60:02d}m {total % 60:02d}s"


# For sort-key positions 1..6: (how the winner's value reads, how another route's value reads).
# Format from docs/DESIGN.md §4.4: "Route B recommended: 0 severe miles vs 18 (A) and 31 (C)."
_CRITERIA: tuple[tuple[Callable[[RouteScore], str], Callable[[RouteScore], str]], ...] = (
    (lambda s: f"{fmt_miles(s.no_travel_mi)} No Travel miles", lambda s: fmt_miles(s.no_travel_mi)),
    (
        lambda s: f"{fmt_miles(s.unknown_mi)} miles without a forecast",
        lambda s: fmt_miles(s.unknown_mi),
    ),
    (lambda s: f"{fmt_miles(s.severe_mi)} severe miles", lambda s: fmt_miles(s.severe_mi)),
    (lambda s: f"{fmt_miles(s.high_mi)} high miles", lambda s: fmt_miles(s.high_mi)),
    (lambda s: f"average risk {_fmt_avg(s)}", _fmt_avg),
    (lambda s: f"travel time {_fmt_time(s)}", _fmt_time),
)
_TIED_ON = (
    "No Travel miles",
    "miles without a forecast",
    "severe miles",
    "high miles",
    "average risk",
)
# Rules whose tie is the normal case when the winner has none of them: not worth saying.
_SKIP_IF_ZERO = {
    "No Travel miles": lambda s: s.no_travel_mi,
    "miles without a forecast": lambda s: s.unknown_mi,
}


def _join(items: Sequence[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def recommend(scores: Sequence[RouteScore]) -> Recommendation:
    """Rank routes and explain the winner by the first rule that separates it from the
    runner-up, e.g. ``Route B recommended: 0 severe miles vs 18 (A) and 31 (C).``"""
    if not scores:
        raise ValueError("recommend() needs at least one route")
    # sorted() is stable, so full ties keep the provider's order.
    ranked = sorted(scores, key=RouteScore.sort_key)
    best = ranked[0]
    all_unsafe = all(s.no_travel_mi > 0 for s in ranked)
    if len(ranked) == 1:
        return Recommendation(ranked, f"{best.label} is the only route available.", all_unsafe)

    rest = ranked[1:]
    best_key, next_key = best.sort_key(), rest[0].sort_key()
    # Positions 0 (the No Travel gate) and 1 (No Travel miles) both read as "No Travel miles";
    # the gate can differ alone when a route has under 0.05 No Travel miles.
    decided_by = next((max(i, 1) for i in range(len(best_key)) if best_key[i] != next_key[i]), None)
    if decided_by is None:
        reason = (
            f"{best.label} recommended: all routes tie on every rule, "
            "so the routing provider's order decides."
        )
        return Recommendation(ranked, reason, all_unsafe)

    show_best, show_other = _CRITERIA[decided_by - 1]
    if decided_by == len(_CRITERIA) and any(_fmt_time(s) == _fmt_time(best) for s in rest):
        show_best, show_other = (lambda s: f"travel time {_fmt_time_s(s)}"), _fmt_time_s
    others = _join([f"{show_other(s)} ({s.route_id})" for s in rest])
    reason = f"{best.label} recommended: {show_best(best)} vs {others}"
    tied = [
        rule
        for rule in _TIED_ON[: decided_by - 1]
        if rule not in _SKIP_IF_ZERO or _SKIP_IF_ZERO[rule](best) > 0
    ]
    if tied:
        reason += f", after tying on {_join(tied)}"
    return Recommendation(ranked, reason + ".", all_unsafe)
