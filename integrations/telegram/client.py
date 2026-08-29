"""
Telegram Bot API client. Like integrations.http_probe, this never raises —
every outcome, including "the library or the network misbehaved", comes
back as a SendResult for the caller to act on.

There's one bot token for the whole platform (settings.TELEGRAM_BOT_TOKEN),
not one per channel — a NotificationChannel only stores which chat_id to
send to, the same bot posts to all of them.
"""

import requests
from django.conf import settings

from integrations.notification_result import SendResult

API_BASE = "https://api.telegram.org"
TIMEOUT_SECONDS = 10


def send_message(chat_id: str, text: str) -> SendResult:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        # Not configured at all — every send will fail the same way until
        # an operator sets the token, so there's nothing to gain from
        # retrying any individual message.
        return SendResult(
            success=False,
            permanent_error=True,
            error_message="TELEGRAM_BOT_TOKEN is not configured.",
        )

    try:
        response = requests.post(
            f"{API_BASE}/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.exceptions.RequestException as exc:
        # A network-level failure to even reach Telegram — worth retrying,
        # it says nothing about whether this particular chat_id is valid.
        return SendResult(success=False, error_message=str(exc))

    if response.status_code == 200:
        return SendResult(success=True)

    try:
        body = response.json()
    except ValueError:
        body = {}
    description = body.get("description") or response.text[:200]

    if response.status_code == 429:
        # Telegram is explicit about how long to back off — respected
        # instead of guessing our own delay.
        retry_after = (body.get("parameters") or {}).get("retry_after")
        return SendResult(success=False, error_message=description, retry_after=retry_after)

    if response.status_code >= 500:
        return SendResult(success=False, error_message=description)

    # Any other 4xx (400 bad request, 403 bot blocked, 404 chat not found)
    # is a fact about this chat_id or this message, not a transient
    # condition — sending the exact same request again would fail the
    # exact same way.
    return SendResult(success=False, permanent_error=True, error_message=description)
