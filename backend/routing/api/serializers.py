"""Request validation for the public API (docs/TECHNICAL_DESIGN.md §3.3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from rest_framework import serializers

from routing.domain.checkpoints import ALLOWED_INTERVALS_MI

MAX_LOAD_LB = 80_000
DEPART_PAST_LIMIT = timedelta(hours=1)
DEPART_FUTURE_LIMIT = timedelta(days=7)


class LocationField(serializers.Field):  # type: ignore[type-arg]
    """Free text (geocoded server-side) or ``{lat, lng, label}`` from autocomplete."""

    default_error_messages = {
        "invalid": "Enter a place name or an object with lat, lng and label.",
        "blank": "This field may not be blank.",
        "too_long": "Place name must be at most 255 characters.",
        "range": "lat must be within -90..90 and lng within -180..180.",
    }

    def to_internal_value(self, data: Any) -> str | dict[str, Any]:
        if isinstance(data, str):
            text = data.strip()
            if not text:
                self.fail("blank")
            if len(text) > 255:
                self.fail("too_long")
            return text
        if isinstance(data, dict):
            try:
                lat, lng = float(data["lat"]), float(data["lng"])
            except (KeyError, TypeError, ValueError):
                self.fail("invalid")
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                self.fail("range")
            label = str(data.get("label") or f"{lat:.4f}, {lng:.4f}")[:255]
            return {"lat": lat, "lng": lng, "label": label}
        self.fail("invalid")

    def to_representation(self, value: Any) -> Any:
        return value


class PlanCreateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    origin = LocationField()
    destination = LocationField()
    depart_at = serializers.CharField()
    load_lb = serializers.IntegerField(min_value=1, max_value=MAX_LOAD_LB)
    interval_mi = serializers.ChoiceField(choices=ALLOWED_INTERVALS_MI, default=25)

    def validate_depart_at(self, value: str) -> datetime:
        try:
            dt = datetime.fromisoformat(value)
        except ValueError as exc:
            raise serializers.ValidationError(
                "Use ISO 8601, e.g. 2026-10-21T08:00:00-05:00."
            ) from exc
        if dt.tzinfo is None:
            # Never guess a timezone: the truck's ETAs depend on it.
            raise serializers.ValidationError("Include a UTC offset, e.g. -05:00 or Z.")
        now = datetime.now(UTC)
        if dt < now - DEPART_PAST_LIMIT:
            raise serializers.ValidationError("Departure can be at most 1 hour in the past.")
        if dt > now + DEPART_FUTURE_LIMIT:
            raise serializers.ValidationError(
                "Departure must be within the next 7 days (forecast range)."
            )
        return dt.astimezone(UTC)


class GeocodeQuerySerializer(serializers.Serializer):  # type: ignore[type-arg]
    q = serializers.CharField(min_length=3, max_length=100, trim_whitespace=True)
    limit = serializers.IntegerField(min_value=1, max_value=10, default=5)
