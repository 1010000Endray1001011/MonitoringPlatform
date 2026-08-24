"""Read-side queries for Incident. `open_incident_for_monitor` in particular
is the one place both the resolve path (processor.py) and the open-guard
(services.py) look up "is there currently an open incident for this
monitor" — one query, reused, rather than two slightly different ones that
could drift."""

from datetime import datetime

from django.db.models import OuterRef, Q, QuerySet, Subquery

from apps.monitors.models import Monitor

from .models import Incident

# An incident is still "open" from the API/engine's point of view in both
# of these statuses — only RESOLVED means it's actually over.
OPEN_STATUSES = [Incident.Status.OPEN, Incident.Status.ACKNOWLEDGED]


def incidents_for_user(user) -> QuerySet[Incident]:
    return Incident.objects.filter(monitor__user=user)


def open_incident_for_monitor(monitor: Monitor) -> Incident | None:
    return Incident.objects.filter(monitor=monitor, status__in=OPEN_STATUSES).first()


def annotate_open_incident_id(monitor_queryset: QuerySet[Monitor]) -> QuerySet[Monitor]:
    """Add `open_incident_id` to a Monitor queryset with one extra query,
    not one extra query per row — same Subquery pattern as
    apps.checks.selectors.annotate_last_response_time, for the same reason.
    """
    open_incident = Incident.objects.filter(
        monitor=OuterRef("pk"), status__in=OPEN_STATUSES
    ).order_by("-started_at")
    return monitor_queryset.annotate(open_incident_id=Subquery(open_incident.values("id")[:1]))


def incident_windows_for_monitor(
    monitor: Monitor, *, start: datetime, end: datetime
) -> list[tuple[datetime, datetime | None]]:
    """`(started_at, resolved_at)` pairs for every incident touching
    `monitor` that overlaps `[start, end)` at all — an incident overlaps if
    it started before the window ends, and either resolved after the
    window started or hasn't resolved yet. Shared by the hourly rollup
    (downtime_seconds) and the /stats endpoint (incidents_count), so the
    overlap rule itself only has to be right in one place.
    """
    incidents = Incident.objects.filter(monitor=monitor, started_at__lt=end).filter(
        Q(resolved_at__gt=start) | Q(resolved_at__isnull=True)
    )
    return list(incidents.values_list("started_at", "resolved_at"))
