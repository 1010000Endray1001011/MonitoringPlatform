import pytest
from django.core.exceptions import ValidationError

from apps.notifications.models import NotificationChannel


def test_email_channel_requires_an_email_key():
    channel = NotificationChannel(type=NotificationChannel.ChannelType.EMAIL, config={})

    with pytest.raises(ValidationError):
        channel.clean()


def test_email_channel_with_an_email_key_is_valid():
    channel = NotificationChannel(
        type=NotificationChannel.ChannelType.EMAIL, config={"email": "a@example.com"}
    )

    channel.clean()  # must not raise


def test_telegram_channel_is_valid_with_an_empty_config():
    # A chat_id cannot exist yet: Telegram bots can't message someone who
    # hasn't written to them first, so the id only arrives once the user
    # taps the connect link and the bot receives their /start. Until then
    # the channel is a placeholder, which is what is_verified=False says.
    channel = NotificationChannel(type=NotificationChannel.ChannelType.TELEGRAM, config={})

    channel.clean()  # must not raise


def test_telegram_channel_with_a_declared_username_is_valid():
    channel = NotificationChannel(
        type=NotificationChannel.ChannelType.TELEGRAM, config={"username": "someone"}
    )

    channel.clean()  # must not raise


def test_str_shows_name_and_type():
    channel = NotificationChannel(
        name="My channel", type=NotificationChannel.ChannelType.EMAIL, config={}
    )

    assert str(channel) == "My channel (EMAIL)"
