"""
Exercises the exact sequence documented in README.md's "Try it by hand"
walkthrough end to end, so a change to the API that breaks the README
fails a test instead of being caught by a reader following stale
instructions. FakeHttpProbe stands in for the real network call the way it
does everywhere else in this suite.
"""

import pytest
from rest_framework import status

from apps.checks import tasks as checks_tasks
from apps.checks.models import CheckResult
from apps.incidents.models import Incident
from integrations.http_probe import FakeHttpProbe, ProbeResult

pytestmark = pytest.mark.django_db


def test_the_documented_walkthrough_works_end_to_end(
    api_client, django_capture_on_commit_callbacks, monkeypatch, settings
):
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False
    # Mirrors what the real probe would compute for a monitor that expects
    # 404 but example.com (as ever) answers 200 — a status mismatch, not a
    # network failure.
    fake = FakeHttpProbe(
        ProbeResult(
            success=False,
            status_code=200,
            response_time_ms=10,
            error_type=CheckResult.ErrorType.UNEXPECTED_STATUS,
        )
    )
    monkeypatch.setattr(checks_tasks, "get_http_probe", lambda: fake)

    register = api_client.post(
        "/api/v1/auth/register",
        {
            "email": "dev@example.com",
            "password": "S0me-Str0ng-Pass",
            "password_confirm": "S0me-Str0ng-Pass",
        },
    )
    assert register.status_code == status.HTTP_201_CREATED

    token = api_client.post(
        "/api/v1/auth/token", {"email": "dev@example.com", "password": "S0me-Str0ng-Pass"}
    )
    assert token.status_code == status.HTTP_200_OK
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")

    channel = api_client.post(
        "/api/v1/notification-channels/",
        {"type": "EMAIL", "name": "My alerts", "config": {"email": "dev@example.com"}},
        format="json",
    )
    assert channel.status_code == status.HTTP_201_CREATED, channel.data
    channel_id = channel.data["id"]

    verify = api_client.post(f"/api/v1/notification-channels/{channel_id}/verify/")
    assert verify.status_code == status.HTTP_200_OK
    assert verify.data["is_verified"] is True

    monitor = api_client.post(
        "/api/v1/monitors/",
        {
            "name": "Always down",
            "url": "https://example.com/",
            "expected_status": 404,
            "failure_threshold": 1,
            "notification_channel_ids": [channel_id],
        },
        format="json",
    )
    assert monitor.status_code == status.HTTP_201_CREATED, monitor.data
    monitor_id = monitor.data["id"]

    with django_capture_on_commit_callbacks(execute=True):
        check_now = api_client.post(f"/api/v1/monitors/{monitor_id}/check/")
    assert check_now.status_code == status.HTTP_202_ACCEPTED

    checks = api_client.get(f"/api/v1/monitors/{monitor_id}/checks/")
    assert checks.status_code == status.HTTP_200_OK
    assert checks.data["results"], "expected at least one recorded check"
    assert checks.data["results"][0]["success"] is False  # got 200, wanted 404

    incidents = api_client.get(f"/api/v1/incidents/?monitor={monitor_id}")
    assert incidents.status_code == status.HTTP_200_OK
    assert len(incidents.data["results"]) == 1
    assert incidents.data["results"][0]["status"] == Incident.Status.OPEN

    detail = api_client.get(f"/api/v1/monitors/{monitor_id}/")
    assert detail.status_code == status.HTTP_200_OK
    assert detail.data["open_incident_id"] == incidents.data["results"][0]["id"]
