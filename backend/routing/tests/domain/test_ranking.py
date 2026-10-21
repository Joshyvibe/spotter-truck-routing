import pytest

from routing.domain.ranking import ScoredSegment, recommend, score_route
from routing.domain.types import Level

L, M, H, S, NT = Level.LOW, Level.MODERATE, Level.HIGH, Level.SEVERE, Level.NO_TRAVEL


def route(rid, duration_s=3600, **miles):
    names = {"low": L, "moderate": M, "high": H, "severe": S, "no_travel": NT, "unknown": None}
    segs = [ScoredSegment(names[k], v) for k, v in miles.items()]
    return score_route(rid, f"Route {rid}", duration_s, segs)


def test_scores_and_distance_weighted_avg():
    r = route("A", low=50, high=25, severe=25)  # research-note worked example
    assert (r.severe_mi, r.high_mi) == (25, 25)
    assert r.avg_risk == pytest.approx(1.25)


def test_unknown_miles_are_excluded_from_avg():
    r = route("A", low=50, high=50, unknown=100)
    assert r.unknown_mi == 100
    assert r.avg_risk == pytest.approx(1.0)


def test_no_forecast_at_all_ranks_after_known():
    rec = recommend([route("A", unknown=100), route("B", low=60, moderate=40)])
    assert rec.best.route_id == "B"


def test_rule1_fewest_severe_miles_beats_faster_route():
    rec = recommend(
        [
            route("A", duration_s=33_000, low=35, high=40, severe=25),
            route("B", duration_s=36_300, low=40, high=60),
        ]
    )
    assert rec.best.route_id == "B"
    assert rec.reason == "Route B recommended: 0 severe miles vs 25 (A)."


def test_rule2_fewest_high_miles():
    rec = recommend([route("A", low=50, high=50), route("B", low=80, high=10, moderate=10)])
    assert rec.best.route_id == "B"
    assert (
        rec.reason == "Route B recommended: 10 high miles vs 50 (A), after tying on severe miles."
    )


def test_rule3_avg_risk_research_example():
    # Research note table: B and C tie on severe/high, C wins on avg risk despite +35 min.
    b = route("B", duration_s=36_300, low=40, high=60)  # avg 1.20
    c = route("C", duration_s=38_400, low=50, high=60)  # avg 1.09
    rec = recommend([b, c])
    assert rec.best.route_id == "C"
    assert rec.reason == (
        "Route C recommended: average risk 1.09 vs 1.20 (B), "
        "after tying on severe miles and high miles."
    )


def test_rule4_shortest_time():
    rec = recommend([route("A", duration_s=5000, low=100), route("B", duration_s=4000, low=100)])
    assert rec.best.route_id == "B"
    assert rec.reason == (
        "Route B recommended: travel time 1h 07m vs 1h 23m (A), "
        "after tying on severe miles, high miles and average risk."
    )


def test_no_travel_gate_sits_above_severe():
    rec = recommend(
        [
            route("A", duration_s=1000, low=99, no_travel=1),
            route("B", duration_s=9000, low=10, severe=90),
        ]
    )
    assert rec.best.route_id == "B"
    assert not rec.all_routes_unsafe
    assert rec.reason == "Route B recommended: 0 No Travel miles vs 1 (A)."


def test_all_routes_unsafe_still_ranked():
    rec = recommend([route("A", low=50, no_travel=30), route("B", low=70, no_travel=10)])
    assert rec.all_routes_unsafe
    assert rec.best.route_id == "B"


def test_float_noise_does_not_decide():
    rec = recommend(
        [
            route("A", duration_s=4000, low=100, severe=0.00001),
            route("B", duration_s=5000, low=100),
        ]
    )
    assert rec.best.route_id == "A"  # severe ties at 0.0, then time decides


def test_full_tie_keeps_provider_order():
    rec = recommend([route("A", low=100), route("B", low=100)])
    assert [s.route_id for s in rec.ranked] == ["A", "B"]
    assert "tie on every rule" in rec.reason


def test_reason_lists_all_other_routes():
    rec = recommend(
        [route("A", low=82, severe=18), route("B", low=100), route("C", low=69, severe=31)]
    )
    # The exact sentence from docs/DESIGN.md §4.4.
    assert rec.reason == "Route B recommended: 0 severe miles vs 18 (A) and 31 (C)."


def test_single_route():
    rec = recommend([route("A", low=10)])
    assert rec.reason == "Route A is the only route available."


def test_tiny_no_travel_stretch_is_named_by_the_gate():
    # 0.03 No Travel mi rounds to 0.0 in the key, but the gate still ranks A last.
    rec = recommend([route("A", low=99.97, no_travel=0.03), route("B", low=50, severe=50)])
    assert rec.best.route_id == "B"
    assert rec.reason == "Route B recommended: 0 No Travel miles vs <0.1 (A)."


def test_travel_time_under_a_minute_apart_shows_seconds():
    rec = recommend([route("A", duration_s=3610, low=100), route("B", duration_s=3600, low=100)])
    assert rec.best.route_id == "B"
    assert rec.reason.startswith("Route B recommended: travel time 1h 00m 00s vs 1h 00m 10s (A)")


def test_route_without_forecast_never_beats_a_checked_route():
    # D7: UNKNOWN is never treated as Low, so 100% unknown loses even to known severe miles.
    rec = recommend([route("A", low=90, severe=10), route("B", unknown=100)])
    assert rec.best.route_id == "A"
    assert rec.reason == "Route A recommended: 0 miles without a forecast vs 100 (B)."


def test_fewer_unknown_miles_wins_then_the_briefs_order():
    rec = recommend(
        [
            route("A", low=60, unknown=40),
            route("B", low=90, unknown=10, severe=0),
        ]
    )
    assert rec.best.route_id == "B"
    # equal unknown miles -> the brief's order decides as usual
    rec = recommend(
        [route("A", low=80, high=10, unknown=10), route("B", low=85, high=5, unknown=10)]
    )
    assert rec.best.route_id == "B"
    assert rec.reason == (
        "Route B recommended: 5 high miles vs 10 (A), "
        "after tying on miles without a forecast and severe miles."
    )


def test_no_travel_gate_still_comes_before_unknown_miles():
    rec = recommend([route("A", low=99, no_travel=1), route("B", unknown=100)])
    assert rec.best.route_id == "B"
