from uuid import uuid4

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class TripPlan(models.Model):
    """One planned trip: inputs plus the full result as JSON (docs/DESIGN.md §5).

    The result is written once, read whole and never queried by checkpoint, so normalising
    routes/checkpoints into tables would add joins with no reader that needs them.
    Change when: analytics across checkpoints ("all Severe checkpoints on I-80 last week").
    """

    INTERVAL_CHOICES = [(10, "10 mi"), (25, "25 mi"), (50, "50 mi")]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    origin_text = models.CharField(max_length=255)
    destination_text = models.CharField(max_length=255)
    origin = models.JSONField()  # {lat, lng, label}
    destination = models.JSONField()
    depart_at = models.DateTimeField()  # stored UTC
    load_lb = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(80_000)]
    )
    interval_mi = models.PositiveSmallIntegerField(choices=INTERVAL_CHOICES, default=25)
    forecast_as_of = models.DateTimeField()
    result = models.JSONField()  # routes, checkpoints, scores, recommendation
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.origin_text} → {self.destination_text} @ {self.depart_at:%Y-%m-%d %H:%M}Z"
