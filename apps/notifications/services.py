"""
Application/service layer for notification channels and delivery.

- create/update/delete channel: ordinary CRUD, same shape as
  apps.monitors.services.
- verify_channel: the one synchronous external call anywhere in this
  system — a user creating a channel is actively waiting to know whether
  it works, unlike every other notification, which goes through the
  outbox below.
- enqueue_incident_notifications / attempt_delivery / mark_delivery_failed:
  the outbox lifecycle. Called from apps.checks.processor (enqueue) and
  apps.notifications.tasks (attempt/mark) — never directly from the API,
  since no user action sends a notification on its own.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.common.exceptions import DomainError

from .models import NotificationChannel, NotificationDelivery
from .providers import get_provider


def _full_clean_or_raise(channel: NotificationChannel) -> None:
    # Same reasoning as apps.monitors.services' identically-named helper:
    # full_clean() raises Django's own ValidationError, which the DRF
    # exception handler doesn't understand — this is the backstop for
    # callers that bypass the serializer (a management command, the admin
    # form doesn't need it, since ModelForm calls full_clean() itself).
    try:
        channel.full_clean()
    except DjangoValidationError as exc:
        details = exc.message_dict if hasattr(exc, "message_dict") else {"__all__": exc.messages}
        raise DomainError("Invalid notification channel configuration.", details=details) from exc


def create_channel(*, user, **fields) -> NotificationChannel:
    channel = NotificationChannel(user=user, **fields)
    _full_clean_or_raise(channel)
    channel.save()
    return channel


def update_channel(*, channel: NotificationChannel, **fields) -> NotificationChannel:
    # A new destination hasn't been proven reachable — verifying the old
    # config said nothing about whatever config is replacing it.
    config_changed = "config" in fields and fields["config"] != channel.config

    for field_name, value in fields.items():
        setattr(channel, field_name, value)
    if config_changed:
        channel.is_verified = False

    _full_clean_or_raise(channel)
    channel.save()
    return channel


def delete_channel(*, channel: NotificationChannel) -> None:
    channel.delete()


def verify_channel(*, channel: NotificationChannel) -> NotificationChannel:
    """Send a real test message right now and record whether it worked —
    the only synchronous provider call in the system, because the user is
    actively waiting on this one instead of it happening in the background.
    """
    provider = get_provider(channel.type)
    result = provider.send(
        channel.config,
        subject="Uptime Monitoring Platform — test notification",
        message="If you can read this, this channel is set up correctly.",
    )

    if result.success:
        channel.is_verified = True
        channel.last_error = None
        channel.last_error_at = None
        channel.save(update_fields=["is_verified", "last_error", "last_error_at", "updated_at"])
        return channel

    channel.last_error = result.error_message
    channel.last_error_at = timezone.now()
    channel.save(update_fields=["last_error", "last_error_at", "updated_at"])
    raise DomainError(
        "Could not deliver a test message to this channel.",
        details={"config": [result.error_message]},
    )


def enqueue_incident_notifications(*, incident, event_type: str) -> None:
    """Create one outbox row per verified, active channel attached to the
    incident's monitor, and schedule its delivery once this transaction
    actually commits.

    `get_or_create` on the (incident, channel, event_type) unique
    constraint makes a second call for the same event a no-op instead of a
    duplicate: apps.checks.processor only ever calls this once per real
    transition, but finding the row already there and doing nothing is a
    far better failure mode than a second message going out if that
    guarantee were ever violated.
    """
    from .tasks import deliver_notification

    channels = incident.monitor.notification_channels.filter(is_verified=True, is_active=True)
    for channel in channels:
        delivery, created = NotificationDelivery.objects.get_or_create(
            incident=incident, channel=channel, event_type=event_type
        )
        if created:
            transaction.on_commit(
                lambda delivery_id=delivery.id: deliver_notification.delay(delivery_id)
            )


def attempt_delivery(*, delivery: NotificationDelivery):
    """One delivery attempt. Returns the SendResult, or None if there was
    nothing to do — already sent, already failed, or already being
    attempted by another worker right now.

    The conditional UPDATE below (flip to SENDING only if still PENDING)
    is what makes a redelivered Celery task harmless: a second worker
    picking up a duplicate of this exact task updates zero rows and
    returns immediately instead of sending a second message.
    """
    claimed = NotificationDelivery.objects.filter(
        id=delivery.id, status=NotificationDelivery.Status.PENDING
    ).update(status=NotificationDelivery.Status.SENDING, attempts=F("attempts") + 1)
    if not claimed:
        return None

    delivery.refresh_from_db()
    provider = get_provider(delivery.channel.type)
    subject, message = _render_message(delivery)
    result = provider.send(delivery.channel.config, subject=subject, message=message)

    if result.success:
        delivery.status = NotificationDelivery.Status.SENT
        delivery.sent_at = timezone.now()
        delivery.last_error = None
    elif result.permanent_error:
        delivery.status = NotificationDelivery.Status.FAILED
        delivery.last_error = result.error_message
    else:
        # Back to PENDING, not left on SENDING — a future retry (a fresh
        # task execution, possibly on a different worker) needs to be able
        # to claim this row the same way this attempt just did.
        delivery.status = NotificationDelivery.Status.PENDING
        delivery.last_error = result.error_message
    delivery.save(update_fields=["status", "sent_at", "last_error", "updated_at"])

    return result


def mark_delivery_failed(*, delivery: NotificationDelivery, error_message: str) -> None:
    delivery.status = NotificationDelivery.Status.FAILED
    delivery.last_error = error_message
    delivery.save(update_fields=["status", "last_error", "updated_at"])


def _render_message(delivery: NotificationDelivery) -> tuple[str, str]:
    incident = delivery.incident
    monitor = incident.monitor

    if delivery.event_type == NotificationDelivery.EventType.INCIDENT_OPENED:
        subject = f"[DOWN] {monitor.name}"
        message = (
            f"{monitor.name} ({monitor.url}) has been down "
            f"since {incident.started_at.isoformat()}."
        )
        if incident.trigger_error_type:
            message += f" Reason: {incident.trigger_error_type}."
        return subject, message

    subject = f"[RESOLVED] {monitor.name}"
    message = f"{monitor.name} ({monitor.url}) recovered at {incident.resolved_at.isoformat()}."
    if incident.duration_seconds is not None:
        message += f" Total downtime: {incident.duration_seconds} seconds."
    return subject, message
