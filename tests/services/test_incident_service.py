from datetime import timedelta

import pytest
from django.utils import timezone

from apps.common.exceptions import ConflictError
from apps.incidents import services
from apps.incidents.models import Incident
from tests.factories import IncidentFactory, MonitorFactory

pytestmark = pytest.mark.django_db


def test_open_incident_creates_a_new_open_incident():
    monitor = MonitorFactory()
    started_at = timezone.now()

    incident = services.open_incident(
        monitor=monitor,
        started_at=started_at,
        trigger_error_type="TIMEOUT",
        trigger_status_code=None,
        failed_checks_count=2,
    )

    assert incident.status == Incident.Status.OPEN
    assert incident.started_at == started_at
    assert incident.failed_checks_count == 2


def test_open_incident_is_idempotent_when_one_is_already_open():
    monitor = MonitorFactory()
    existing = services.open_incident(
        monitor=monitor,
        started_at=timezone.now(),
        trigger_error_type="TIMEOUT",
        trigger_status_code=None,
        failed_checks_count=2,
    )

    # Calling it again for the same monitor must not raise (the partial
    # unique index would reject a genuine duplicate) and must not create
    # a second row — it returns the one that's already open instead.
    again = services.open_incident(
        monitor=monitor,
        started_at=timezone.now(),
        trigger_error_type="CONNECTION_REFUSED",
        trigger_status_code=None,
        failed_checks_count=5,
    )

    assert again.id == existing.id
    assert Incident.objects.filter(monitor=monitor).count() == 1


def test_resolve_incident_sets_status_and_duration():
    started_at = timezone.now() - timedelta(minutes=10)
    incident = IncidentFactory(status=Incident.Status.OPEN, started_at=started_at)
    resolved_at = timezone.now()

    resolved = services.resolve_incident(
        incident=incident,
        resolved_at=resolved_at,
        resolution_source=Incident.ResolutionSource.AUTO_RECOVERY,
    )

    assert resolved.status == Incident.Status.RESOLVED
    assert resolved.resolved_at == resolved_at
    assert resolved.duration_seconds == 600


def test_resolve_an_already_resolved_incident_raises_conflict():
    incident = IncidentFactory(status=Incident.Status.RESOLVED, resolved_at=timezone.now())

    with pytest.raises(ConflictError):
        services.resolve_incident(
            incident=incident,
            resolved_at=timezone.now(),
            resolution_source=Incident.ResolutionSource.AUTO_RECOVERY,
        )


def test_acknowledge_incident_sets_status_and_timestamp():
    incident = IncidentFactory(status=Incident.Status.OPEN)

    acknowledged = services.acknowledge_incident(incident=incident)

    assert acknowledged.status == Incident.Status.ACKNOWLEDGED
    assert acknowledged.acknowledged_at is not None


def test_acknowledge_a_non_open_incident_raises_conflict():
    incident = IncidentFactory(status=Incident.Status.ACKNOWLEDGED, acknowledged_at=timezone.now())

    with pytest.raises(ConflictError):
        services.acknowledge_incident(incident=incident)


def test_acknowledged_at_survives_resolution():
    incident = IncidentFactory(status=Incident.Status.OPEN)
    services.acknowledge_incident(incident=incident)

    resolved = services.resolve_incident(
        incident=incident,
        resolved_at=timezone.now(),
        resolution_source=Incident.ResolutionSource.AUTO_RECOVERY,
    )

    assert resolved.acknowledged_at is not None
