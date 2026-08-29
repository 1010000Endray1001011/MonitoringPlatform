"""
`deliver_notification` tested the same way as `run_check` in
tests/tasks/test_run_check.py: direct calls / `.apply()`, with
`apps.notifications.providers.EmailProvider.send` monkeypatched instead of
making real calls. `CELERY_TASK_ALWAYS_EAGER` means `.apply()`'s retry
handling (raising `Retry`) is visible synchronously, same as for run_check.
"""

import pytest
from celery.exceptions import Retry

from apps.incidents.models import Incident
from apps.notifications.models import NotificationDelivery
from apps.notifications.tasks import deliver_notification
from integrations.notification_result import SendResult
from tests.factories import IncidentFactory, NotificationChannelFactory

pytestmark = pytest.mark.django_db


def _delivery(**overrides):
    incident = overrides.pop("incident", None) or IncidentFactory(status=Incident.Status.OPEN)
    channel = overrides.pop("channel", None) or NotificationChannelFactory()
    defaults = dict(
        incident=incident,
        channel=channel,
        event_type=NotificationDelivery.EventType.INCIDENT_OPENED,
    )
    defaults.update(overrides)
    return NotificationDelivery.objects.create(**defaults)


def _patch_send(monkeypatch, result: SendResult):
    monkeypatch.setattr(
        "apps.notifications.providers.EmailProvider.send",
        lambda self, config, *, subject, message: result,
    )


def test_successful_delivery_marks_sent(monkeypatch):
    delivery = _delivery()
    _patch_send(monkeypatch, SendResult(success=True))

    deliver_notification(delivery.id)

    delivery.refresh_from_db()
    assert delivery.status == NotificationDelivery.Status.SENT


def test_a_missing_delivery_is_handled_silently(monkeypatch):
    _patch_send(monkeypatch, SendResult(success=True))

    deliver_notification("00000000-0000-0000-0000-000000000000")  # must not raise


def test_permanent_error_marks_failed_without_retrying(monkeypatch):
    delivery = _delivery()
    _patch_send(
        monkeypatch, SendResult(success=False, permanent_error=True, error_message="bad address")
    )

    deliver_notification(delivery.id)  # must not raise Retry

    delivery.refresh_from_db()
    assert delivery.status == NotificationDelivery.Status.FAILED
    assert delivery.last_error == "bad address"


def test_temporary_error_raises_retry(monkeypatch):
    delivery = _delivery()
    _patch_send(monkeypatch, SendResult(success=False, error_message="timeout"))

    with pytest.raises(Retry):
        deliver_notification.apply(args=[delivery.id])

    delivery.refresh_from_db()
    # Still PENDING, not FAILED — the retry that was just requested is
    # expected to pick this row back up.
    assert delivery.status == NotificationDelivery.Status.PENDING


def test_exhausting_retries_marks_failed_instead_of_retrying_forever(monkeypatch):
    delivery = _delivery()
    _patch_send(monkeypatch, SendResult(success=False, error_message="still failing"))

    # Simulate this being the final allowed attempt.
    monkeypatch.setattr(deliver_notification, "max_retries", 0)

    deliver_notification.apply(args=[delivery.id])  # must not raise Retry

    delivery.refresh_from_db()
    assert delivery.status == NotificationDelivery.Status.FAILED


def test_retry_after_from_the_provider_is_used_as_the_backoff(monkeypatch):
    delivery = _delivery()
    _patch_send(
        monkeypatch, SendResult(success=False, error_message="rate limited", retry_after=42)
    )

    with pytest.raises(Retry) as excinfo:
        deliver_notification.apply(args=[delivery.id])

    assert excinfo.value.when == 42
