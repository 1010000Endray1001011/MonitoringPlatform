"""
Three serializers for three different jobs, on purpose —
one "do everything" ModelSerializer would either leak engine-owned fields
into write requests or force list responses to carry detail-only fields:

- MonitorListSerializer   read-only, what `GET /monitors/` returns per row
- MonitorDetailSerializer read-only, what `GET /monitors/{id}/` returns
- MonitorWriteSerializer  input only, what POST/PATCH accept
- MonitorStatusSerializer read-only, the small body pause/resume return

`last_response_time_ms`, `open_incident_id`, `uptime_24h`,
`avg_response_time_24h_ms` and `notification_channels`
"""

from rest_framework import serializers

from .models import Monitor


def _compute_status(monitor: Monitor) -> str:
    """The client-facing status combines two independently-owned fields:
     `is_enabled` (user) wins as PAUSED when off, otherwise it's
    exactly the engine's `health_status`. One function so the three
    serializers below can't compute this differently from each other.
    """
    return "PAUSED" if not monitor.is_enabled else monitor.health_status


class MonitorListSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = Monitor
        fields = [
            "id",
            "name",
            "url",
            "method",
            "expected_status",
            "interval_seconds",
            "timeout_seconds",
            "is_enabled",
            "status",
            "last_checked_at",
            "next_check_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_status(self, obj: Monitor) -> str:
        return _compute_status(obj)


class MonitorDetailSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = Monitor
        fields = [
            "id",
            "name",
            "url",
            "method",
            "expected_status",
            "interval_seconds",
            "timeout_seconds",
            "headers",
            "failure_threshold",
            "success_threshold",
            "is_enabled",
            "status",
            "consecutive_failures",
            "consecutive_successes",
            "last_checked_at",
            "next_check_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_status(self, obj: Monitor) -> str:
        return _compute_status(obj)


class MonitorWriteSerializer(serializers.ModelSerializer):
    """Input-only: create/update go through apps.monitors.services, never
    `serializer.save()` — see the ViewSet. This class's own `.create()`/
    `.update()` are therefore never called; it exists purely to validate
    and to shape `validated_data` into service kwargs.

    `name`/`url` end up required because the model gives them no default;
    everything else is optional here because the model field already has
    one (DRF's ModelSerializer derives `required` from that automatically).
    """

    class Meta:
        model = Monitor
        fields = [
            "name",
            "url",
            "method",
            "expected_status",
            "interval_seconds",
            "timeout_seconds",
            "headers",
            "failure_threshold",
            "success_threshold",
        ]

    def validate(self, attrs: dict) -> dict:
        # Mirrors Monitor.clean() (apps/monitors/models.py) so a bad
        # combination comes back as a normal 400 here rather than reaching
        # the service and failing full_clean() there. On a PATCH that only
        # touches one of the two fields, fall back to the current value of
        # whichever side wasn't part of this request.
        timeout = attrs.get("timeout_seconds", getattr(self.instance, "timeout_seconds", None))
        interval = attrs.get("interval_seconds", getattr(self.instance, "interval_seconds", None))
        if timeout is not None and interval is not None and timeout >= interval:
            raise serializers.ValidationError(
                {"timeout_seconds": "timeout_seconds must be less than interval_seconds."}
            )
        return attrs


class MonitorStatusSerializer(serializers.ModelSerializer):
    """The small body returned by /pause and /resume —
    deliberately not the full detail representation, since those actions
    only ever change `is_enabled` and whatever falls out of it."""

    status = serializers.SerializerMethodField()

    class Meta:
        model = Monitor
        fields = ["id", "status", "is_enabled"]
        read_only_fields = fields

    def get_status(self, obj: Monitor) -> str:
        return _compute_status(obj)
