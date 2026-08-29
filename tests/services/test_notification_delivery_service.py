import pytest
from django.utils import timezone

from apps.incidents.models import Incident
from apps.notifications import services
from apps.notifications.models import NotificationDelivery
from integrations.notification_result import SendResult
from tests.factories import IncidentFactory, NotificationChannelFactory

pytestmark = pytest.mark.django_db


def test_enqueue_creates_a_delivery_per_verified_active_channel():
    incident = IncidentFactory()
    verified = NotificationChannelFactory(is_verified=True, is_active=True)
    verified.monitors.add(incident.monitor)
    unverified = NotificationChannelFactory(is_verified=False, is_active=True)
    unverified.monitors.add(incident.monitor)
    inactive = NotificationChannelFactory(is_verified=True, is_active=False)
    inactive.monitors.add(incident.monitor)

    services.enqueue_incident_notifications(
        incident=incident, event_type=NotificationDelivery.EventType.INCIDENT_OPENED
    )

    deliveries = NotificationDelivery.objects.filter(incident=incident)
    assert deliveries.count() == 1
    assert deliveries.first().channel_id == verified.id


def test_enqueue_is_idempotent_for_the_same_incident_and_event():
    incident = IncidentFactory()
    channel = NotificationChannelFactory(is_verified=True, is_active=True)
    channel.monitors.add(incident.monitor)

    services.enqueue_incident_notifications(
        incident=incident, event_type=NotificationDelivery.EventType.INCIDENT_OPENED
    )
    services.enqueue_incident_notifications(
        incident=incident, event_type=NotificationDelivery.EventType.INCIDENT_OPENED
    )

    assert NotificationDelivery.objects.filter(incident=incident).count() == 1


def test_enqueue_schedules_delivery_only_after_commit(
    django_capture_on_commit_callbacks, monkeypatch
):
    incident = IncidentFactory()
    channel = NotificationChannelFactory(is_verified=True, is_active=True)
    channel.monitors.add(incident.monitor)
    sent = []
    monkeypatch.setattr(
        "apps.notifications.tasks.deliver_notification.delay",
        lambda delivery_id: sent.append(delivery_id),
    )

    services.enqueue_incident_notifications(
        incident=incident, event_type=NotificationDelivery.EventType.INCIDENT_OPENED
    )
    # No django_capture_on_commit_callbacks wrapping this call — the
    # pytest-django test transaction never actually commits, so the
    # on_commit callback must still be pending.
    assert sent == []


def test_attempt_delivery_marks_sent_on_success(monkeypatch):
    incident = IncidentFactory()
    channel = NotificationChannelFactory()
    delivery = NotificationDelivery.objects.create(
        incident=incident,
        channel=channel,
        event_type=NotificationDelivery.EventType.INCIDENT_OPENED,
    )
    monkeypatch.setattr(
        "apps.notifications.providers.EmailProvider.send",
        lambda self, config, *, subject, message: SendResult(success=True),
    )

    result = services.attempt_delivery(delivery=delivery)

    delivery.refresh_from_db()
    assert result.success is True
    assert delivery.status == NotificationDelivery.Status.SENT
    assert delivery.sent_at is not None
    assert delivery.attempts == 1


def test_attempt_delivery_marks_failed_on_a_permanent_error(monkeypatch):
    incident = IncidentFactory()
    channel = NotificationChannelFactory()
    delivery = NotificationDelivery.objects.create(
        incident=incident,
        channel=channel,
        event_type=NotificationDelivery.EventType.INCIDENT_OPENED,
    )
    monkeypatch.setattr(
        "apps.notifications.providers.EmailProvider.send",
        lambda self, config, *, subject, message: SendResult(
            success=False, permanent_error=True, error_message="bad address"
        ),
    )

    services.attempt_delivery(delivery=delivery)

    delivery.refresh_from_db()
    assert delivery.status == NotificationDelivery.Status.FAILED
    assert delivery.last_error == "bad address"


def test_attempt_delivery_leaves_pending_on_a_temporary_error(monkeypatch):
    incident = IncidentFactory()
    channel = NotificationChannelFactory()
    delivery = NotificationDelivery.objects.create(
        incident=incident,
        channel=channel,
        event_type=NotificationDelivery.EventType.INCIDENT_OPENED,
    )
    monkeypatch.setattr(
        "apps.notifications.providers.EmailProvider.send",
        lambda self, config, *, subject, message: SendResult(
            success=False, error_message="timeout"
        ),
    )

    services.attempt_delivery(delivery=delivery)

    delivery.refresh_from_db()
    assert delivery.status == NotificationDelivery.Status.PENDING
    assert delivery.attempts == 1


def test_attempt_delivery_on_an_already_sent_row_is_a_no_op(monkeypatch):
    incident = IncidentFactory()
    channel = NotificationChannelFactory()
    delivery = NotificationDelivery.objects.create(
        incident=incident,
        channel=channel,
        event_type=NotificationDelivery.EventType.INCIDENT_OPENED,
        status=NotificationDelivery.Status.SENT,
    )
    calls = []
    monkeypatch.setattr(
        "apps.notifications.providers.EmailProvider.send",
        lambda self, config, *, subject, message: calls.append(1) or SendResult(success=True),
    )

    result = services.attempt_delivery(delivery=delivery)

    assert result is None
    assert calls == []  # the provider must never be called a second time


def test_render_message_for_incident_opened_mentions_the_trigger():
    incident = IncidentFactory(
        status=Incident.Status.OPEN, trigger_error_type="CONNECTION_REFUSED"
    )
    channel = NotificationChannelFactory()
    delivery = NotificationDelivery.objects.create(
        incident=incident,
        channel=channel,
        event_type=NotificationDelivery.EventType.INCIDENT_OPENED,
    )

    subject, message = services._render_message(delivery)

    assert incident.monitor.name in subject
    assert "CONNECTION_REFUSED" in message


def test_render_message_for_incident_resolved_mentions_the_downtime():
    incident = IncidentFactory(
        status=Incident.Status.RESOLVED, resolved_at=timezone.now(), duration_seconds=125
    )
    channel = NotificationChannelFactory()
    delivery = NotificationDelivery.objects.create(
        incident=incident,
        channel=channel,
        event_type=NotificationDelivery.EventType.INCIDENT_RESOLVED,
    )

    subject, message = services._render_message(delivery)

    assert "RESOLVED" in subject
    assert "125" in message


def test_mark_delivery_failed():
    incident = IncidentFactory()
    channel = NotificationChannelFactory()
    delivery = NotificationDelivery.objects.create(
        incident=incident,
        channel=channel,
        event_type=NotificationDelivery.EventType.INCIDENT_OPENED,
    )

    services.mark_delivery_failed(delivery=delivery, error_message="gave up")

    delivery.refresh_from_db()
    assert delivery.status == NotificationDelivery.Status.FAILED
    assert delivery.last_error == "gave up"
