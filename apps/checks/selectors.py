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


def streak_start_at(monitor: Monitor, *, success: bool, count: int) -> datetime | None:
    """The `checked_at` of the earliest check in the most recent run of
    `count` consecutive checks with the given `success` value.

    Used only at the exact moment processor.py detects a real status
    transition, to find when the crossing streak actually began — not the
    moment it happened to cross the threshold. Filtering by `success`
    explicitly (rather than just taking the last `count` rows regardless
    of outcome) makes the correctness of this query obvious from the code
    itself: processor.py's own staleness guard already ensures the
    monitor's `select_for_update()`'d processing never sees an
    out-of-order result by the time this runs, so the last `count` rows
    with the matching outcome are exactly the streak that just crossed.
    """
    checked_at_values = list(
        CheckResult.objects.filter(monitor=monitor, success=success)
        .order_by("-checked_at")
        .values_list("checked_at", flat=True)[:count]
    )
    return min(checked_at_values) if checked_at_values else None
