"""
Maps a NotificationChannel's `type` to the integration that actually knows
how to reach it. `NotificationProvider` is a `Protocol` — not because
there's some abstract notion of "provider" worth modeling, but because
there are concretely two implementations today and a third
(post-MVP: Slack, webhooks) is expected, and both existing ones need to be
swappable in tests without mocking `requests` or SMTP directly.
"""

from typing import Protocol

from integrations.email import send_email
from integrations.notification_result import SendResult
from integrations.telegram import send_message as send_telegram_message

from .models import NotificationChannel


class NotificationProvider(Protocol):
    def send(self, config: dict, *, subject: str, message: str) -> SendResult: ...


class EmailProvider:
    def send(self, config: dict, *, subject: str, message: str) -> SendResult:
        # Model validation (NotificationChannel.clean) already keeps a
        # freshly-created channel from ever having a config missing this
        # key, but that's a save-time guarantee, not a permanent one — a
        # channel written before a config schema change, or edited by hand
        # through the admin, could still reach here without it. Every
        # provider in this module is required to never raise (see the
        # module docstring's "never mock requests/SMTP directly" premise —
        # callers only ever branch on SendResult), so a config problem is
        # reported the same way a "chat not found" from Telegram is: a
        # permanent error about this specific channel, not a crash.
        email = config.get("email")
        if not email:
            return SendResult(
                success=False, permanent_error=True, error_message="Channel has no email address."
            )
        return send_email(email, subject, message)


class TelegramProvider:
    def send(self, config: dict, *, subject: str, message: str) -> SendResult:
        chat_id = config.get("chat_id")
        if not chat_id:
            return SendResult(
                success=False, permanent_error=True, error_message="Channel has no chat_id."
            )
        # Telegram messages have no separate subject line — folding it
        # into the text is simpler than dropping it on the floor.
        return send_telegram_message(chat_id, f"{subject}\n\n{message}")


_PROVIDERS: dict[str, NotificationProvider] = {
    NotificationChannel.ChannelType.EMAIL: EmailProvider(),
    NotificationChannel.ChannelType.TELEGRAM: TelegramProvider(),
}


def get_provider(channel_type: str) -> NotificationProvider:
    return _PROVIDERS[channel_type]
