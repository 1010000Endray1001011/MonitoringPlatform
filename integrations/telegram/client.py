"""
Telegram Bot API client. Like integrations.http_probe, this never raises —
every outcome, including "the library or the network misbehaved", comes
back as a SendResult for the caller to act on.

There's one bot token for the whole platform (settings.TELEGRAM_BOT_TOKEN),
not one per channel — a NotificationChannel only stores which chat_id to
send to, the same bot posts to all of them.
"""

from dataclasses import dataclass, field

import requests
from django.conf import settings

from integrations.notification_result import SendResult

API_BASE = "https://api.telegram.org"
TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class UpdatesResult:
    """Outcome of one getUpdates call. Same contract as SendResult: this
    module never raises, so a caller only ever branches on `ok`."""

    ok: bool
    updates: list[dict] = field(default_factory=list)
    error_message: str | None = None


def get_updates(*, offset: int | None = None, timeout: int = 0) -> UpdatesResult:
    """Fetch pending updates for the bot.

    `offset` is Telegram's acknowledgement mechanism, not a cursor to page
    with: passing `last_update_id + 1` is what permanently confirms every
    update below it, so anything already handled is never sent again. Skip
    it and Telegram re-sends the same backlog forever.

    `timeout` turns this into a long poll — the request hangs open until an
    update arrives or the timeout expires, which is what makes a claim feel
    instant without polling in a tight loop. The HTTP read timeout is set
    above it so the socket outlives the long poll Telegram is holding.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return UpdatesResult(ok=False, error_message="TELEGRAM_BOT_TOKEN is not configured.")

    params: dict = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset

    try:
        response = requests.get(
            f"{API_BASE}/bot{token}/getUpdates",
            params=params,
            timeout=timeout + TIMEOUT_SECONDS,
        )
    except requests.exceptions.RequestException as exc:
        return UpdatesResult(ok=False, error_message=str(exc))

    try:
        body = response.json()
    except ValueError:
        return UpdatesResult(ok=False, error_message=response.text[:200])

    if response.status_code != 200 or not body.get("ok"):
        # 409 is the one worth recognising by sight: it means a webhook is
        # registered for this bot, and Telegram refuses to serve getUpdates
        # and a webhook at the same time.
        return UpdatesResult(
            ok=False, error_message=body.get("description") or response.text[:200]
        )

    return UpdatesResult(ok=True, updates=body.get("result") or [])


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
