from datetime import timedelta

import pytest
from django.utils import timezone

from apps.incidents.models import Incident
from apps.incidents.tasks import close_stale_incidents
from apps.monitors.models import Monitor
from tests.factories import IncidentFactory, MonitorFactory

pytestmark = pytest.mark.django_db


def test_resolves_an_open_incident_whose_monitor_is_already_up():
    monitor = MonitorFactory(health_status=Monitor.HealthStatus.UP)
    incident = IncidentFactory(monitor=monitor, status=Incident.Status.OPEN)

    close_stale_incidents()

    incident.refresh_from_db()
    assert incident.status == Incident.Status.RESOLVED
    assert incident.resolution_source == Incident.ResolutionSource.SYSTEM_RECONCILE


def test_uses_now_as_resolved_at_not_updated_at():
    monitor = MonitorFactory(health_status=Monitor.HealthStatus.UP)
    stale_started_at = timezone.now() - timedelta(days=3)
    incident = IncidentFactory(
        monitor=monitor, status=Incident.Status.OPEN, started_at=stale_started_at
    )
    before = timezone.now()

    close_stale_incidents()

    incident.refresh_from_db()
    # If this used updated_at (close to created_at/started_at, since
    # nothing else touched the row), duration_seconds would come out
    # near zero instead of reflecting the multi-day gap.
    assert incident.resolved_at >= before
    assert incident.duration_seconds >= int(timedelta(days=3).total_seconds())


def test_leaves_a_genuinely_open_incident_alone_when_the_monitor_is_still_down():
    monitor = MonitorFactory(health_status=Monitor.HealthStatus.DOWN)
    incident = IncidentFactory(monitor=monitor, status=Incident.Status.OPEN)

    close_stale_incidents()

    incident.refresh_from_db()
    assert incident.status == Incident.Status.OPEN


def test_also_resolves_an_acknowledged_incident_left_stale():
    monitor = MonitorFactory(health_status=Monitor.HealthStatus.UP)
    incident = IncidentFactory(
        monitor=monitor,
        status=Incident.Status.ACKNOWLEDGED,
        acknowledged_at=timezone.now(),
    )

    close_stale_incidents()

    incident.refresh_from_db()
    assert incident.status == Incident.Status.RESOLVED
