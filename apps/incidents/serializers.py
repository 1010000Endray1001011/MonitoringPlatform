from rest_framework import serializers

from apps.monitors.models import Monitor

from .models import Incident


class _MonitorSummarySerializer(serializers.ModelSerializer):
    """Just enough of a Monitor to identify it from inside an incident —
    the full monitor is one request away via its own id."""

    class Meta:
        model = Monitor
        fields = ["id", "name", "url"]
        read_only_fields = fields


class IncidentListSerializer(serializers.ModelSerializer):
    monitor = _MonitorSummarySerializer(read_only=True)

    class Meta:
        model = Incident
        fields = [
            "id",
            "monitor",
            "status",
            "started_at",
            "acknowledged_at",
            "resolved_at",
            "duration_seconds",
            "trigger_error_type",
            "trigger_status_code",
            "failed_checks_count",
        ]
        read_only_fields = fields


class IncidentDetailSerializer(serializers.ModelSerializer):
    monitor = _MonitorSummarySerializer(read_only=True)

    class Meta:
        model = Incident
        fields = [
            "id",
            "monitor",
            "status",
            "started_at",
            "acknowledged_at",
            "resolved_at",
            "duration_seconds",
            "trigger_error_type",
            "trigger_status_code",
            "failed_checks_count",
            "resolution_source",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
