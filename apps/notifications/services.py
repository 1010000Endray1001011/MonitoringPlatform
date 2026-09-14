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

import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.common.exceptions import ConflictError, DomainError

from .models import NotificationChannel, NotificationDelivery, TelegramClaim
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
    if channel.type == NotificationChannel.ChannelType.TELEGRAM:
        # A Telegram channel is useless until a chat has been bound to it,
        # and binding needs a link — so the link exists from the moment the
        # channel does, rather than making the caller ask for one.
        issue_telegram_claim(channel=channel)
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
    if channel.type == NotificationChannel.ChannelType.TELEGRAM and not channel.config.get(
        "chat_id"
    ):
        # Nothing to verify yet, and attempting the send would produce a
        # provider error about a missing chat_id — technically accurate,
        # useless as an explanation. The user isn't misconfigured, they
        # just haven't tapped the link yet.
        raise ConflictError(
            "This Telegram channel isn't connected yet — open the connect link and press Start "
            "in the bot first."
        )

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


# --- Telegram chat claiming ------------------------------------------------
#
# A bot can't message a user who hasn't written to it first, so a Telegram
# channel is created empty and filled in when the user taps a one-time link
# and presses Start. Everything below is that handshake: issuing the link,
# and resolving the /start the bot receives back into a bound chat.


def issue_telegram_claim(*, channel: NotificationChannel) -> TelegramClaim:
    """Create (or replace) the one-time link for a Telegram channel.

    Replacing rather than adding: only the most recently issued link should
    work, so a link someone left open in an old tab stops being usable the
    moment a new one is generated.
    """
    TelegramClaim.objects.filter(channel=channel).delete()
    return TelegramClaim.objects.create(
        channel=channel,
        # token_urlsafe stays inside Telegram's allowed alphabet for a
        # /start payload (letters, digits, - and _), so it needs no
        # encoding on the way into the deep link.
        token=secrets.token_urlsafe(24),
        expires_at=timezone.now() + timedelta(minutes=settings.TELEGRAM_CLAIM_TTL_MINUTES),
    )


def telegram_deep_link(*, channel: NotificationChannel) -> str | None:
    """The t.me link to show the user, or None when there's nothing to show
    — already connected, never issued, expired, or no bot username set."""
    # Operators paste the handle the way Telegram shows it — "@name" — but a
    # t.me path takes the bare name. "t.me/@name" is not a valid path, and
    # Telegram does not 404 it: it redirects to its own download page and drops
    # the ?start payload on the way. So the symptom is "the link won't open the
    # app" rather than anything pointing at a stray character in .env. Accept
    # either spelling here instead of relying on the operator to spot it.
    username = settings.TELEGRAM_BOT_USERNAME.strip().lstrip("@")
    if not username:
        return None
    claim = getattr(channel, "telegram_claim", None)
    if claim is None or claim.claimed_at is not None or claim.is_expired():
        return None
    return f"https://t.me/{username}?start={claim.token}"


@dataclass(frozen=True)
class ClaimOutcome:
    """What the bot should say back, and whether anything was bound.

    The reply text lives here rather than in the polling task because the
    decision and the wording are the same thing — "why didn't this work" is
    the only useful thing the bot can tell a user standing in the chat.
    """

    reply: str
    linked: bool = False


def _normalise_username(value: str | None) -> str:
    return (value or "").lstrip("@").strip().lower()


@transaction.atomic
def claim_telegram_chat(*, token: str, chat_id: str, username: str | None) -> ClaimOutcome:
    """Resolve a `/start <token>` into a bound channel.

    Called from the polling task for every incoming start command. Every
    path returns an outcome rather than raising: the caller's job is to
    reply to a person in a chat window, not to handle exceptions.
    """
    try:
        claim = (
            TelegramClaim.objects.select_for_update().select_related("channel").get(token=token)
        )
    except TelegramClaim.DoesNotExist:
        return ClaimOutcome(
            reply=(
                "This connect link isn't valid. Open the Channels page in Uptime Monitoring "
                "Platform and start a new Telegram channel to get a fresh one."
            )
        )

    channel = claim.channel

    if claim.claimed_at is not None:
        # Tapping the same link twice is the most likely repeat, and it's
        # harmless — but only for the chat that already owns it.
        if str(channel.config.get("chat_id")) == str(chat_id):
            return ClaimOutcome(reply=f"'{channel.name}' is already connected to this chat.")
        return ClaimOutcome(reply="This connect link has already been used.")

    if claim.is_expired():
        return ClaimOutcome(
            reply=(
                "This connect link has expired. Open the Channels page and press "
                "'Get a new link' to generate another one."
            )
        )

    expected = _normalise_username(channel.config.get("username"))
    actual = _normalise_username(username)
    if expected and expected != actual:
        # The declared username is a cross-check, not the identity: the
        # token already proved which channel this is. Refusing on mismatch
        # is what makes "I said @me, so I get @me" literally true.
        return ClaimOutcome(
            reply=(
                f"This link expects @{expected}, but you're signed in as "
                f"{('@' + actual) if actual else 'an account with no username'}. "
                "Nothing was connected."
            )
        )

    channel.config = {**channel.config, "chat_id": str(chat_id)}
    if actual:
        # Record what Telegram actually reported, so the channel shows the
        # real account rather than whatever was typed into the form.
        channel.config["username"] = actual
    channel.is_verified = True
    channel.last_error = None
    channel.last_error_at = None
    channel.save(
        update_fields=["config", "is_verified", "last_error", "last_error_at", "updated_at"]
    )

    claim.claimed_at = timezone.now()
    claim.save(update_fields=["claimed_at", "updated_at"])

    return ClaimOutcome(
        reply=f"'{channel.name}' is connected. Incident alerts will arrive here.",
        linked=True,
    )
