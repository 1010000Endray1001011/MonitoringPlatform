"""
The two custom admin actions (force_resolve, force_acknowledge) are the
only real logic in IncidentAdmin — everything else is permission
boilerplate. Exercised through the actual admin changelist URL (not by
calling the ModelAdmin methods directly) so this also proves a superuser
can run them despite has_change_permission being False.
"""

import pytest
from django.urls import reverse

from apps.incidents.models import Incident
from tests.factories import IncidentFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_user():
    return UserFactory(is_staff=True, is_superuser=True)


def test_force_resolve_action_resolves_selected_incidents(client, admin_user):
    client.force_login(admin_user)
    incident = IncidentFactory(status=Incident.Status.OPEN)

    response = client.post(
        reverse("admin:incidents_incident_changelist"),
        {"action": "force_resolve", "_selected_action": [str(incident.id)]},
        follow=True,
    )

    assert response.status_code == 200
    incident.refresh_from_db()
    assert incident.status == Incident.Status.RESOLVED
    assert incident.resolution_source == Incident.ResolutionSource.SYSTEM_RECONCILE


def test_force_resolve_action_skips_already_resolved_incidents(client, admin_user):
    client.force_login(admin_user)
    incident = IncidentFactory(status=Incident.Status.RESOLVED)

    # Must not raise (the action excludes already-resolved rows from what
    # it processes) — resolve_incident's own ConflictError would surface
    # as a 500 if that exclusion were ever removed.
    response = client.post(
        reverse("admin:incidents_incident_changelist"),
        {"action": "force_resolve", "_selected_action": [str(incident.id)]},
        follow=True,
    )

    assert response.status_code == 200


def test_force_acknowledge_action_acknowledges_selected_incidents(client, admin_user):
    client.force_login(admin_user)
    incident = IncidentFactory(status=Incident.Status.OPEN)

    response = client.post(
        reverse("admin:incidents_incident_changelist"),
        {"action": "force_acknowledge", "_selected_action": [str(incident.id)]},
        follow=True,
    )

    assert response.status_code == 200
    incident.refresh_from_db()
    assert incident.status == Incident.Status.ACKNOWLEDGED
