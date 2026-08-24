import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.incidents.models import Incident
from tests.factories import IncidentFactory

pytestmark = pytest.mark.django_db


def test_partial_unique_index_rejects_a_second_open_incident_for_the_same_monitor():
    first = IncidentFactory(status=Incident.Status.OPEN)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Incident.objects.create(
                monitor=first.monitor,
                status=Incident.Status.OPEN,
                started_at=timezone.now(),
            )


def test_partial_unique_index_allows_a_resolved_and_a_new_open_incident_together():
    monitor = IncidentFactory(status=Incident.Status.RESOLVED).monitor

    # A RESOLVED incident doesn't count against the constraint — a new one
    # can open for the same monitor without conflict.
    Incident.objects.create(
        monitor=monitor, status=Incident.Status.OPEN, started_at=timezone.now()
    )


def test_str_shows_monitor_status_and_start_time():
    incident = IncidentFactory(status=Incident.Status.OPEN)

    text = str(incident)

    assert str(incident.monitor_id) in text
    assert "OPEN" in text
