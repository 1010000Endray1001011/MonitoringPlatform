from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from apps.checks import tasks
from apps.checks.models import CheckResult
from integrations.http_probe import FakeHttpProbe
from tests.factories import CheckResultFactory, MonitorFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_history_is_ordered_newest_first(authenticated_client, user):
    monitor = MonitorFactory(user=user)
    older = CheckResultFactory(monitor=monitor, checked_at=timezone.now() - timedelta(hours=1))
    newer = CheckResultFactory(monitor=monitor, checked_at=timezone.now())

    response = authenticated_client.get(f"/api/v1/monitors/{monitor.id}/checks/")

    assert response.status_code == status.HTTP_200_OK
    ids = [row["id"] for row in response.data["results"]]
    assert ids == [newer.id, older.id]


def test_filter_by_success(authenticated_client, user):
    monitor = MonitorFactory(user=user)
    CheckResultFactory(monitor=monitor, success=True)
    CheckResultFactory(
        monitor=monitor, success=False, status_code=None, error_type=CheckResult.ErrorType.TIMEOUT
    )

    response = authenticated_client.get(f"/api/v1/monitors/{monitor.id}/checks/?success=false")

    assert response.data["results"], "expected at least one failed check in the response"
    assert all(row["success"] is False for row in response.data["results"])


def test_filter_by_error_type(authenticated_client, user):
    monitor = MonitorFactory(user=user)
    CheckResultFactory(
        monitor=monitor, success=False, status_code=None, error_type=CheckResult.ErrorType.TIMEOUT
    )
    CheckResultFactory(
        monitor=monitor,
        success=False,
        status_code=None,
        error_type=CheckResult.ErrorType.CONNECTION_REFUSED,
    )

    response = authenticated_client.get(
        f"/api/v1/monitors/{monitor.id}/checks/?error_type=TIMEOUT"
    )

    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["error_type"] == "TIMEOUT"


def test_filter_by_since(authenticated_client, user):
    monitor = MonitorFactory(user=user)
    old = CheckResultFactory(monitor=monitor, checked_at=timezone.now() - timedelta(days=10))
    recent = CheckResultFactory(monitor=monitor, checked_at=timezone.now())
    cutoff = (timezone.now() - timedelta(days=1)).isoformat()

    # Passed as `data=` rather than hand-built into the URL string so the
    # test client URL-encodes it — a raw "+00:00" UTC offset in a query
    # string decodes as a literal space, which silently breaks parsing.
    response = authenticated_client.get(
        f"/api/v1/monitors/{monitor.id}/checks/", data={"since": cutoff}
    )

    ids = [row["id"] for row in response.data["results"]]
    assert recent.id in ids
    assert old.id not in ids


def test_filter_by_until(authenticated_client, user):
    monitor = MonitorFactory(user=user)
    old = CheckResultFactory(monitor=monitor, checked_at=timezone.now() - timedelta(days=10))
    recent = CheckResultFactory(monitor=monitor, checked_at=timezone.now())
    cutoff = (timezone.now() - timedelta(days=1)).isoformat()

    response = authenticated_client.get(
        f"/api/v1/monitors/{monitor.id}/checks/", data={"until": cutoff}
    )

    ids = [row["id"] for row in response.data["results"]]
    assert old.id in ids
    assert recent.id not in ids


def test_history_for_another_user_s_monitor_is_not_visible(authenticated_client):
    other_monitor = MonitorFactory(user=UserFactory())
    CheckResultFactory(monitor=other_monitor)

    response = authenticated_client.get(f"/api/v1/monitors/{other_monitor.id}/checks/")

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_manual_check_returns_202_and_enqueues_a_probe(
    authenticated_client, user, django_capture_on_commit_callbacks, monkeypatch
):
    monitor = MonitorFactory(user=user, is_enabled=True)
    fake = FakeHttpProbe()
    monkeypatch.setattr(tasks, "get_http_probe", lambda: fake)

    with django_capture_on_commit_callbacks(execute=True):
        response = authenticated_client.post(f"/api/v1/monitors/{monitor.id}/check/")

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert "poll_url" in response.data
    assert len(fake.calls) == 1


def test_manual_check_on_a_paused_monitor_returns_409(authenticated_client, user):
    monitor = MonitorFactory(user=user, is_enabled=False)

    response = authenticated_client.post(f"/api/v1/monitors/{monitor.id}/check/")

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["error"]["code"] == "conflict"


def test_manual_check_on_another_user_s_monitor_returns_404(authenticated_client):
    other_monitor = MonitorFactory(user=UserFactory())

    response = authenticated_client.post(f"/api/v1/monitors/{other_monitor.id}/check/")

    assert response.status_code == status.HTTP_404_NOT_FOUND
