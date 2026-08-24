"""Read-side queries for CheckResult — the history a monitor's detail page
and history endpoint are built from."""

from datetime import datetime

from django.db.models import OuterRef, QuerySet, Subquery

from apps.monitors.models import Monitor

from .models import CheckResult


def annotate_last_response_time(monitor_queryset: QuerySet[Monitor]) -> QuerySet[Monitor]:
    """Add `last_response_time_ms` to a Monitor queryset with one extra
    query, not one extra query per row.

    A correlated subquery rather than a Python-side loop or a `.filter()`
    per monitor: this runs as part of the same single SQL query that
    fetches the monitors themselves, so serializing a list of 100 monitors
    costs the same one round trip whether this annotation is used or not.
    """
    latest_result = CheckResult.objects.filter(monitor=OuterRef("pk")).order_by("-checked_at")
    return monitor_queryset.annotate(
        last_response_time_ms=Subquery(latest_result.values("response_time_ms")[:1])
    )


def check_results_for_monitor(
    monitor: Monitor,
    *,
    success: bool | None = None,
    error_type: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> QuerySet[CheckResult]:
    queryset = CheckResult.objects.filter(monitor=monitor)
    if success is not None:
        queryset = queryset.filter(success=success)
    if error_type is not None:
        queryset = queryset.filter(error_type=error_type)
    if since is not None:
        queryset = queryset.filter(checked_at__gte=since)
    if until is not None:
        queryset = queryset.filter(checked_at__lte=until)
    return queryset
