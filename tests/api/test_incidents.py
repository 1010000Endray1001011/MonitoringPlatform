import pytest
from rest_framework import status

from apps.incidents.models import Incident
from tests.factories import IncidentFactory, MonitorFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_list_only_returns_the_caller_s_own_incidents(authenticated_client, user):
    IncidentFactory(monitor=MonitorFactory(user=user))
    IncidentFactory(monitor=MonitorFactory(user=UserFactory()))

    response = authenticated_client.get("/api/v1/incidents/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1


def test_filter_by_status(authenticated_client, user):
    IncidentFactory(monitor=MonitorFactory(user=user), status=Incident.Status.OPEN)
    IncidentFactory(
        monitor=MonitorFactory(user=user), status=Incident.Status.RESOLVED, resolved_at=None
    )

    response = authenticated_client.get("/api/v1/incidents/?status=OPEN")

    assert response.data["count"] == 1
    assert response.data["results"][0]["status"] == "OPEN"


def test_detail_includes_resolution_source(authenticated_client, user):
    incident = IncidentFactory(monitor=MonitorFactory(user=user))

    response = authenticated_client.get(f"/api/v1/incidents/{incident.id}/")

    assert response.status_code == status.HTTP_200_OK
    assert "resolution_source" in response.data
    assert response.data["monitor"]["id"] == str(incident.monitor_id)


def test_other_users_incident_is_never_visible(authenticated_client):
    other_incident = IncidentFactory(monitor=MonitorFactory(user=UserFactory()))

    for response in (
        authenticated_client.get(f"/api/v1/incidents/{other_incident.id}/"),
        authenticated_client.post(f"/api/v1/incidents/{other_incident.id}/acknowledge/"),
    ):
        assert response.status_code == status.HTTP_404_NOT_FOUND


def test_acknowledge_an_open_incident(authenticated_client, user):
    incident = IncidentFactory(monitor=MonitorFactory(user=user), status=Incident.Status.OPEN)

    response = authenticated_client.post(f"/api/v1/incidents/{incident.id}/acknowledge/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "ACKNOWLEDGED"


def test_acknowledging_twice_returns_409(authenticated_client, user):
    incident = IncidentFactory(monitor=MonitorFactory(user=user), status=Incident.Status.OPEN)
    authenticated_client.post(f"/api/v1/incidents/{incident.id}/acknowledge/")

    response = authenticated_client.post(f"/api/v1/incidents/{incident.id}/acknowledge/")

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["error"]["code"] == "conflict"


def test_unauthenticated_request_is_rejected(api_client):
    response = api_client.get("/api/v1/incidents/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
