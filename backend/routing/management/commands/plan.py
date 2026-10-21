"""Plan a trip from the command line: ``manage.py plan "Chicago, IL" "Denver, CO" --load 42000``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from django.core.management.base import BaseCommand, CommandParser

from routing.domain.ranking import format_duration
from routing.providers.registry import geocoding_provider, routing_provider, weather_provider
from routing.services.geocode import resolve
from routing.services.plan_trip import PlanInputs, plan_trip


class Command(BaseCommand):
    help = "Plan a trip and print the 3 scored routes"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("origin")
        parser.add_argument("destination")
        parser.add_argument("--load", type=int, default=42_000, help="load weight, lb")
        parser.add_argument("--interval", type=int, default=25, choices=(10, 25, 50))
        parser.add_argument("--depart-in-hours", type=float, default=1.0)

    def handle(self, *args: object, **opts: object) -> None:
        geo = geocoding_provider()
        depart = datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(
            hours=float(opts["depart_in_hours"])  # type: ignore[arg-type]
        )
        inputs = PlanInputs(
            origin=resolve(geo, str(opts["origin"])),
            destination=resolve(geo, str(opts["destination"])),
            depart_at=depart,
            load_lb=int(opts["load"]),  # type: ignore[call-overload]
            interval_mi=int(opts["interval"]),  # type: ignore[call-overload]
        )
        plan = plan_trip(inputs, routing_provider(), weather_provider())
        w = self.stdout.write
        w(
            f"{plan['origin']['label']} → {plan['destination']['label']}  "
            f"depart {plan['depart_at']}  load {plan['load_lb']:,} lb  "
            f"every {plan['interval_mi']} mi"
        )
        w(f"Forecast as of {plan['forecast_as_of']}\n")
        w(
            f"{'':3}{'route':8}{'miles':>8}{'time':>10}{'NT':>7}{'sev':>7}{'high':>7}"
            f"{'mod':>7}{'low':>8}{'unk':>6}{'avg':>6}  cps"
        )
        for r in plan["routes"]:
            s = r["summary"]
            star = " * " if r["is_recommended"] else "   "
            avg = "-" if s["avg_risk"] is None else f"{s['avg_risk']:.2f}"
            w(
                f"{star}{r['label']:8}{r['distance_mi']:>8.1f}{format_duration(r['duration_s']):>10}"
                f"{s['no_travel_mi']:>7.1f}{s['severe_mi']:>7.1f}{s['high_mi']:>7.1f}"
                f"{s['moderate_mi']:>7.1f}{s['low_mi']:>8.1f}{s['unknown_mi']:>6.1f}{avg:>6}"
                f"  {len(r['checkpoints'])}"
            )
        w(f"\n{plan['recommendation_reason']}")
        for warning in plan["warnings"]:
            w(f"! {warning}")
        worst = max(
            (c for r in plan["routes"] for c in r["checkpoints"]),
            key=lambda c: (
                ["LOW", "MODERATE", "HIGH", "SEVERE", "NO_TRAVEL", "UNKNOWN"].index(c["level"])
                if c["level"] != "UNKNOWN"
                else -1
            ),
        )
        w(f"Worst checkpoint: mile {worst['mile']} at {worst['eta']}: {worst['reason']}")
