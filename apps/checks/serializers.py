from rest_framework import serializers

from .models import CheckResult


class CheckResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckResult
        fields = [
            "id",
            "checked_at",
            "success",
            "status_code",
            "response_time_ms",
            "error_type",
            "error_message",
            "response_size_bytes",
        ]
        read_only_fields = fields


class ImmediateCheckAcceptedSerializer(serializers.Serializer):
    """Shape of the 202 response from triggering an out-of-schedule check —
    there's no object to represent, just an acknowledgement and where to
    look for the result once it exists."""

    detail = serializers.CharField(read_only=True)
    poll_url = serializers.CharField(read_only=True)


class PeriodSummarySerializer(serializers.Serializer):
    """Mirrors apps.checks.stats.PeriodSummary — schema-only, the view
    builds the actual response from that dataclass directly rather than
    instantiating this serializer at runtime."""

    uptime_ratio = serializers.FloatField(allow_null=True)
    checks_total = serializers.IntegerField()
    checks_failed = serializers.IntegerField()
    avg_response_time_ms = serializers.IntegerField(allow_null=True)
    p95_response_time_ms = serializers.IntegerField(allow_null=True)
    incidents_count = serializers.IntegerField()
    total_downtime_seconds = serializers.IntegerField()


class StatsSeriesBucketSerializer(serializers.Serializer):
    bucket = serializers.CharField()
    checks_total = serializers.IntegerField()
    checks_failed = serializers.IntegerField()
    avg_response_time_ms = serializers.IntegerField(allow_null=True)
    p95_response_time_ms = serializers.IntegerField(allow_null=True)


class MonitorStatsSerializer(serializers.Serializer):
    monitor_id = serializers.UUIDField()
    period = serializers.CharField()
    period_from = serializers.DateTimeField()
    period_to = serializers.DateTimeField()
    summary = PeriodSummarySerializer()
    series = StatsSeriesBucketSerializer(many=True)
