import pytest
from rest_framework import status

from tests.factories import MonitorFactory, MonitorHourlyStatFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("period", ["24h", "7d", "30d"])
def test_stats_returns_200_for_every_supported_period(authenticated_client, user, period):
    monitor = MonitorFactory(user=user)
    MonitorHourlyStatFactory(monitor=monitor)

    response = authenticated_client.get(f"/api/v1/monitors/{monitor.id}/stats/?period={period}")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["period"] == period
    assert "summary" in response.data
    assert "series" in response.data


def test_stats_defaults_to_24h(authenticated_client, user):
    monitor = MonitorFactory(user=user)

    response = authenticated_client.get(f"/api/v1/monitors/{monitor.id}/stats/")

    assert response.data["period"] == "24h"


def test_stats_with_no_data_does_not_500(authenticated_client, user):
    monitor = MonitorFactory(user=user)

    response = authenticated_client.get(f"/api/v1/monitors/{monitor.id}/stats/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["summary"]["checks_total"] == 0
    assert response.data["summary"]["uptime_ratio"] is None
    assert response.data["series"] == []


def test_stats_rejects_an_unrecognised_period(authenticated_client, user):
    monitor = MonitorFactory(user=user)

    response = authenticated_client.get(f"/api/v1/monitors/{monitor.id}/stats/?period=bogus")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"]["code"] == "validation_error"


def test_stats_for_another_users_monitor_returns_404(authenticated_client):
    other_monitor = MonitorFactory(user=UserFactory())

    response = authenticated_client.get(f"/api/v1/monitors/{other_monitor.id}/stats/")

    assert response.status_code == status.HTTP_404_NOT_FOUND
