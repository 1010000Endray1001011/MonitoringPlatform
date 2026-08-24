"""Reconciliation safety net — not part of the normal incident lifecycle,
which is entirely driven by apps.checks.processor reacting to status
transitions. This exists only to catch a desync that shouldn't happen but
would otherwise leave an incident stuck open forever if it did."""

from celery import shared_task
from django.utils import timezone

from apps.monitors.models import Monitor

from . import services
from .models import Incident
from .selectors import OPEN_STATUSES


@shared_task(name="apps.incidents.tasks.close_stale_incidents")
def close_stale_incidents() -> None:
    stale = Incident.objects.filter(
        status__in=OPEN_STATUSES, monitor__health_status=Monitor.HealthStatus.UP
    )
    for incident in stale:
        # timezone.now(), not incident.updated_at: the whole point of this
        # task is catching an incident that's been open through an
        # undetected desync, and updated_at could be sitting right next to
        # started_at if nothing ever touched the row since it opened —
        # that would report a near-zero duration for an outage that may
        # have lasted a long time. "Recovered by now, exact moment
        # unknown" is the honest signal here, not a guess dressed up as
        # a precise timestamp.
        services.resolve_incident(
            incident=incident,
            resolved_at=timezone.now(),
            resolution_source=Incident.ResolutionSource.SYSTEM_RECONCILE,
        )
