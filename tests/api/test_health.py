import pytest
from rest_framework import status

pytestmark = pytest.mark.django_db


def test_health_reports_ok_when_dependencies_available(api_client):
    response = api_client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "ok"
    assert response.data["database"] == "ok"
    assert response.data["redis"] == "ok"


def test_health_is_public(api_client):
    response = api_client.get("/health")

    assert response.status_code != status.HTTP_401_UNAUTHORIZED
