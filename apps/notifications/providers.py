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
        return send_email(config["email"], subject, message)


class TelegramProvider:
    def send(self, config: dict, *, subject: str, message: str) -> SendResult:
        # Telegram messages have no separate subject line — folding it
        # into the text is simpler than dropping it on the floor.
        return send_telegram_message(config["chat_id"], f"{subject}\n\n{message}")


_PROVIDERS: dict[str, NotificationProvider] = {
    NotificationChannel.ChannelType.EMAIL: EmailProvider(),
    NotificationChannel.ChannelType.TELEGRAM: TelegramProvider(),
}


def get_provider(channel_type: str) -> NotificationProvider:
    return _PROVIDERS[channel_type]
