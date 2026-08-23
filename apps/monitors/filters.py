"""
`status` (PAUSED|NEW|UP|DOWN) isn't a real database column,
it's `_compute_status()` from serializers.py applied to `is_enabled` +
`health_status`. django-filter can't derive a filter for a computed field
automatically, so this translates the client-facing value back into the two
real columns by hand. Search (`name`/`url`) and ordering are plain DRF
backends configured directly on the ViewSet — they don't need this kind of
translation.
"""

import django_filters

from .models import Monitor


class MonitorFilterSet(django_filters.FilterSet):
    status = django_filters.CharFilter(method="filter_status")

    class Meta:
        model = Monitor
        fields = ["status"]

    def filter_status(self, queryset, name, value):
        value = value.upper()
        if value == "PAUSED":
            return queryset.filter(is_enabled=False)
        if value in Monitor.HealthStatus.values:
            return queryset.filter(is_enabled=True, health_status=value)
        # An unrecognised status value matches nothing rather than raising —
        # simpler than a second error-response shape just for a filter typo.
        return queryset.none()
