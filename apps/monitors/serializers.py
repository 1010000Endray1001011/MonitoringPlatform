"""
Four serializers for four different jobs, on purpose — one "do everything"
ModelSerializer would either leak engine-owned fields into write requests
or force list responses to carry detail-only fields:

- MonitorListSerializer   read-only, what `GET /monitors/` returns per row
- MonitorDetailSerializer read-only, what `GET /monitors/{id}/` returns
- MonitorWriteSerializer  input only, what POST/PATCH accept
- MonitorStatusSerializer read-only, the small body pause/resume return

Every field that was once deferred pending a model that didn't exist yet
(`last_response_time_ms`, `open_incident_id`, `uptime_24h`,
`avg_response_time_24h_ms`, `notification_channels`) now has one to read
from.
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.checks.models import MonitorHourlyStat
from apps.checks.stats import summarize_period
from apps.notifications.models import NotificationChannel

from .models import Monitor


class _NotificationChannelSummarySerializer(serializers.ModelSerializer):
    """Just enough of a channel to identify it from inside a monitor — the
    full channel (config, verification state) is one request away."""

    class Meta:
        model = NotificationChannel
        fields = ["id", "type", "name"]
        read_only_fields = fields


def _compute_status(monitor: Monitor) -> str:
    """The client-facing status combines two independently-owned fields:
     `is_enabled` (user) wins as PAUSED when off, otherwise it's
    exactly the engine's `health_status`. One function so the three
    serializers below can't compute this differently from each other.
    """
    return "PAUSED" if not monitor.is_enabled else monitor.health_status


class MonitorListSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    # Neither of these is a model field — both are populated by
    # annotations the ViewSet adds to its queryset
    # (apps.checks.selectors.annotate_last_response_time,
    # apps.incidents.selectors.annotate_open_incident_id), so they're
    # plain declared fields rather than something Meta.fields could pick
    # up automatically from the model.
    last_response_time_ms = serializers.IntegerField(read_only=True, allow_null=True)
    open_incident_id = serializers.UUIDField(read_only=True, allow_null=True)

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
            "last_response_time_ms",
            "open_incident_id",
            "next_check_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_status(self, obj: Monitor) -> str:
        return _compute_status(obj)


class MonitorDetailSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    last_response_time_ms = serializers.IntegerField(read_only=True, allow_null=True)
    open_incident_id = serializers.UUIDField(read_only=True, allow_null=True)
    uptime_24h = serializers.SerializerMethodField()
    avg_response_time_24h_ms = serializers.SerializerMethodField()
    # The real M2M reverse accessor (NotificationChannel.monitors'
    # related_name) — declared explicitly because the default DRF would
    # otherwise render it as a bare list of ids, not this nested summary.
    notification_channels = _NotificationChannelSummarySerializer(many=True, read_only=True)

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
            "last_response_time_ms",
            "open_incident_id",
            "uptime_24h",
            "avg_response_time_24h_ms",
            "notification_channels",
            "next_check_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_status(self, obj: Monitor) -> str:
        return _compute_status(obj)

    def get_uptime_24h(self, obj: Monitor) -> float | None:
        return self._last_24h_summary(obj).uptime_ratio

    def get_avg_response_time_24h_ms(self, obj: Monitor) -> int | None:
        return self._last_24h_summary(obj).avg_response_time_ms

    def _last_24h_summary(self, obj: Monitor):
        # Memoized on the serializer instance: get_uptime_24h and
        # get_avg_response_time_24h_ms both need this, and the detail view
        # only ever serializes one monitor per request, so caching here
        # (rather than in the ViewSet, like the annotation-based fields
        # above) is enough to avoid running the same query twice.
        if not hasattr(self, "_cached_24h_summary"):
            since = timezone.now() - timedelta(hours=24)
            hourly_stats = list(
                MonitorHourlyStat.objects.filter(monitor=obj, hour_start__gte=since)
            )
            # incidents_count isn't used by either field that reads this
            # summary — 0 is a throwaway value, not a real count.
            self._cached_24h_summary = summarize_period(hourly_stats, incidents_count=0)
        return self._cached_24h_summary


class MonitorWriteSerializer(serializers.ModelSerializer):
    """Input-only: create/update go through apps.monitors.services, never
    `serializer.save()` — see the ViewSet. This class's own `.create()`/
    `.update()` are therefore never called; it exists purely to validate
    and to shape `validated_data` into service kwargs.

    `name`/`url` end up required because the model gives them no default;
    everything else is optional here because the model field already has
    one (DRF's ModelSerializer derives `required` from that automatically).
    """

    # write_only + a field name that doesn't match the model's own
    # `notification_channels` (the M2M itself): `validated_data` ends up
    # with a literal `notification_channel_ids` key, matching the keyword
    # apps.monitors.services.create_monitor/update_monitor already expect,
    # with no `source=` indirection needed.
    notification_channel_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=NotificationChannel.objects.none(),
        required=False,
        write_only=True,
    )

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
            "notification_channel_ids",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The empty queryset above is just a placeholder so the field can
        # be declared before a request exists (e.g. during schema
        # generation) — scoped to the actual caller here, so a monitor can
        # never be wired up to another user's notification channel.
        #
        # `many=True` on a RelatedField doesn't return that field itself —
        # `PrimaryKeyRelatedField.__new__` intercepts it and returns a
        # `ManyRelatedField` wrapping the real field as `.child_relation`.
        # The queryset lives on that inner field; setting `.queryset` on
        # the wrapper is a silent no-op; every provided id then fails
        # validation against the empty placeholder queryset instead.
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            channel_field = self.fields["notification_channel_ids"]
            channel_field.child_relation.queryset = NotificationChannel.objects.filter(
                user=request.user
            )

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
