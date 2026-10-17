"""Validation for the /api/trips/analyze request."""
import math
from datetime import datetime, timedelta, timezone

from rest_framework import serializers

MAX_LOAD_LB = 80_000
MAX_DAYS_AHEAD = 7


class AnalyzeRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(min_length=2, max_length=200)
    destination = serializers.CharField(min_length=2, max_length=200)
    departure_time = serializers.CharField()
    load_weight_lb = serializers.FloatField(min_value=0, max_value=MAX_LOAD_LB)
    checkpoint_interval_mi = serializers.ChoiceField(choices=[10, 25, 50], default=25)
    # Absent or null means a normal live analysis. "storm" asks for the simulated demo.
    demo_scenario = serializers.ChoiceField(choices=["storm"], allow_null=True, default=None)

    def validate_load_weight_lb(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError("Enter a valid number.")
        return value

    def validate_departure_time(self, value):
        try:
            dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            raise serializers.ValidationError(
                "Use ISO 8601, e.g. 2026-10-20T08:00:00+01:00."
            ) from None
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise serializers.ValidationError("Include a UTC offset, e.g. +01:00 or Z.")
        now = datetime.now(timezone.utc)
        if dt < now - timedelta(minutes=5):
            raise serializers.ValidationError("Departure time is in the past.")
        if dt > now + timedelta(days=MAX_DAYS_AHEAD):
            raise serializers.ValidationError(
                f"Departure must be within the next {MAX_DAYS_AHEAD} days."
            )
        return dt.astimezone(timezone.utc)