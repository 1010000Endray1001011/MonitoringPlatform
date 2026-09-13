"""
The Celery side of delivery — deliberately thin, same philosophy as
apps.checks.tasks: the actual logic (claiming a delivery, calling the
provider, deciding what the outcome means) lives in
apps.notifications.services and is tested without Celery at all. This
task's only job is turning a SendResult into a retry/give-up decision.
"""

import logging
import random

from celery import shared_task
from django.conf import settings
from django.core.cache import cache

from integrations import telegram

from . import services
from .models import NotificationDelivery

logger = logging.getLogger(__name__)

# max_retries=4 means 5 total attempts (1 initial + 4 retries) before a
# temporary failure is finally given up on as FAILED.
MAX_RETRIES = 4


def _backoff_seconds(retry_number: int) -> int:
    """Exponential backoff with jitter: roughly 1m, 2m, 4m, 8m. The jitter
    (up to 10% extra) exists so a batch of deliveries that all failed at
    the same moment — one provider outage affecting several channels —
    don't all retry at exactly the same moment again."""
    base = 60 * (2**retry_number)
    return int(base + random.uniform(0, base * 0.1))


@shared_task(
    name="apps.notifications.tasks.deliver_notification",
    bind=True,
    max_retries=MAX_RETRIES,
    # Safe to redeliver: attempt_delivery's conditional UPDATE (PENDING ->
    # SENDING) means a duplicate execution of this exact task finds
    # nothing left to do rather than sending a second message. That's what
    # makes acks_late=True the right call here, unlike run_check — losing
    # this task outright would mean an incident nobody gets told about,
    # which is worse than the (already-guarded-against) risk of a
    # redelivery.
    acks_late=True,
)
def deliver_notification(self, delivery_id) -> None:
    try:
        delivery = NotificationDelivery.objects.select_related("channel", "incident__monitor").get(
            id=delivery_id
        )
    except NotificationDelivery.DoesNotExist:
        return

    log_context = {
        "delivery_id": str(delivery_id),
        "monitor_id": str(delivery.incident.monitor_id),
        "channel_type": delivery.channel.type,
    }

    result = services.attempt_delivery(delivery=delivery)
    if result is None or result.success or result.permanent_error:
        # Nothing left to do, it worked, or retrying would be pointless —
        # attempt_delivery already recorded the right terminal status (or
        # left the row exactly as some other worker's attempt did).
        if result is not None:
            level = logging.INFO if result.success else logging.WARNING
            logger.log(level, "notification delivery finished", extra=log_context)
        return

    if self.request.retries >= self.max_retries:
        logger.warning("notification delivery exhausted retries", extra=log_context)
        services.mark_delivery_failed(
            delivery=delivery,
            error_message=result.error_message or "delivery failed after all retries",
        )
        return

    countdown = result.retry_after or _backoff_seconds(self.request.retries)
    logger.info(
        "notification delivery temporarily failed, retrying",
        extra={**log_context, "countdown": countdown},
    )
    raise self.retry(
        exc=RuntimeError(result.error_message or "temporary delivery failure"),
        countdown=countdown,
    )


# --- Telegram inbound ------------------------------------------------------

# Long poll: the request hangs open until Telegram has something or this
# many seconds pass. It's what makes pressing Start feel immediate without
# hammering the API — and it's why this task can be scheduled at a leisurely
# interval rather than a tight one.
LONG_POLL_SECONDS = 25

# Comfortably longer than one long poll, so the lock always outlives the
# request holding it, but short enough that a worker killed mid-poll frees
# it within one scheduling cycle.
POLL_LOCK_TTL_SECONDS = 60

POLL_LOCK_KEY = "telegram:getupdates:lock"
POLL_OFFSET_KEY = "telegram:getupdates:offset"


def _parse_start_command(update: dict) -> tuple[str, str, str | None] | None:
    """`(payload, chat_id, username)` for a `/start` message, else None.

    Everything else the bot might receive — group joins, edits, ordinary
    chatter — is not an error, it's simply not part of this handshake.
    """
    message = update.get("message") or {}
    text = (message.get("text") or "").strip()
    if not text.startswith("/start"):
        return None

    chat_id = (message.get("chat") or {}).get("id")
    if chat_id is None:
        return None

    parts = text.split(maxsplit=1)
    payload = parts[1].strip() if len(parts) > 1 else ""
    username = (message.get("from") or {}).get("username")
    return payload, str(chat_id), username


@shared_task(name="apps.notifications.tasks.poll_telegram_updates")
def poll_telegram_updates() -> None:
    """Receive `/start` commands and bind the chats that sent them.

    Runs on the schedule rather than as a dedicated process: Celery beat is
    already running, and a bot that only ever handles a connect handshake
    doesn't justify another service in the stack.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        return

    # Telegram allows exactly one getUpdates consumer at a time and answers
    # a second concurrent call with 409 Conflict. Beat can overlap this
    # task with itself (the long poll outlasts nothing, but a slow worker
    # or a redelivered task can), so the lock is what keeps that from
    # turning into a stream of 409s.
    if not cache.add(POLL_LOCK_KEY, "1", timeout=POLL_LOCK_TTL_SECONDS):
        return

    try:
        result = telegram.get_updates(offset=cache.get(POLL_OFFSET_KEY), timeout=LONG_POLL_SECONDS)
        if not result.ok:
            logger.warning("Telegram getUpdates failed: %s", result.error_message)
            return

        for update in result.updates:
            _handle_update(update)

        if result.updates:
            # Acknowledge everything just handled. Stored with no expiry:
            # losing it means Telegram re-sends up to 24h of updates, which
            # is survivable only because claiming is idempotent — a repeat
            # of an already-claimed token answers "already connected"
            # rather than binding anything a second time.
            cache.set(POLL_OFFSET_KEY, result.updates[-1]["update_id"] + 1, timeout=None)
    finally:
        cache.delete(POLL_LOCK_KEY)


def _handle_update(update: dict) -> None:
    parsed = _parse_start_command(update)
    if parsed is None:
        return
    payload, chat_id, username = parsed

    if not payload:
        # A bare /start — someone found the bot on their own rather than
        # through a connect link. Telling them where to get one is more
        # useful than silence.
        telegram.send_message(
            chat_id,
            "Open the Channels page in Uptime Monitoring Platform, add a Telegram channel, "
            "and tap the connect link it gives you.",
        )
        return

    outcome = services.claim_telegram_chat(token=payload, chat_id=chat_id, username=username)
    telegram.send_message(chat_id, outcome.reply)
    if outcome.linked:
        logger.info("Telegram chat linked", extra={"chat_id": chat_id})
