"""
Only the two scoped rates get exercised end-to-end here (monitor_check and
auth_token) — they're low enough to hit within a handful of requests. The
blanket anon/user rates (20/min, 120/min) are asserted at the unit level
instead (test_fail_open_throttling.py): actually driving 21+ requests
through the API just to prove DRF's own, unmodified throttle math works
would be slow and wouldn't tell us anything about *our* code.
"""

import pytest
from rest_framework import status

from tests.factories import MonitorFactory

pytestmark = pytest.mark.django_db


def test_monitor_check_is_throttled_after_the_scoped_limit(authenticated_client, user, settings):
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False
    monitor = MonitorFactory(user=user)
    url = f"/api/v1/monitors/{monitor.id}/check/"

    for _ in range(5):
        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_202_ACCEPTED

    response = authenticated_client.post(url)

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.data["error"]["code"] == "throttled"
    assert response.data["retry_after"] is not None


def test_auth_token_is_throttled_after_the_scoped_limit(api_client, user):
    body = {"email": user.email, "password": "wrong-password"}

    for _ in range(10):
        api_client.post("/api/v1/auth/token", body)

    response = api_client.post("/api/v1/auth/token", body)

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
