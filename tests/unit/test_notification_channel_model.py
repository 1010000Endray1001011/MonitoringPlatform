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


def test_telegram_channel_requires_a_chat_id_key():
    channel = NotificationChannel(type=NotificationChannel.ChannelType.TELEGRAM, config={})

    with pytest.raises(ValidationError):
        channel.clean()


def test_telegram_channel_with_a_chat_id_key_is_valid():
    channel = NotificationChannel(
        type=NotificationChannel.ChannelType.TELEGRAM, config={"chat_id": "12345"}
    )

    channel.clean()  # must not raise


def test_str_shows_name_and_type():
    channel = NotificationChannel(
        name="My channel", type=NotificationChannel.ChannelType.EMAIL, config={}
    )

    assert str(channel) == "My channel (EMAIL)"
