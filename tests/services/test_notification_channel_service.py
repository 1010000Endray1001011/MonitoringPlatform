import pytest

from apps.common.exceptions import DomainError
from apps.notifications import services
from apps.notifications.models import NotificationChannel
from integrations.notification_result import SendResult
from tests.factories import NotificationChannelFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_create_channel():
    user = UserFactory()

    channel = services.create_channel(
        user=user,
        type=NotificationChannel.ChannelType.EMAIL,
        name="My email",
        config={"email": "a@example.com"},
    )

    assert channel.user == user
    assert channel.is_verified is False


def test_create_channel_rejects_a_config_that_does_not_match_the_type():
    user = UserFactory()

    with pytest.raises(DomainError):
        services.create_channel(
            user=user,
            type=NotificationChannel.ChannelType.EMAIL,
            name="Bad",
            config={"chat_id": "12345"},
        )


def test_update_channel_changing_config_resets_verification():
    channel = NotificationChannelFactory(is_verified=True, config={"email": "old@example.com"})

    updated = services.update_channel(channel=channel, config={"email": "new@example.com"})

    assert updated.is_verified is False


def test_update_channel_without_touching_config_keeps_verification():
    channel = NotificationChannelFactory(is_verified=True, name="Original")

    updated = services.update_channel(channel=channel, name="Renamed")

    assert updated.is_verified is True
    assert updated.name == "Renamed"


def test_delete_channel_removes_the_row():
    channel = NotificationChannelFactory()
    channel_id = channel.id

    services.delete_channel(channel=channel)

    assert not NotificationChannel.objects.filter(id=channel_id).exists()


def test_verify_channel_marks_it_verified_on_success(monkeypatch):
    channel = NotificationChannelFactory(is_verified=False)
    monkeypatch.setattr(
        "apps.notifications.providers.EmailProvider.send",
        lambda self, config, *, subject, message: SendResult(success=True),
    )

    verified = services.verify_channel(channel=channel)

    assert verified.is_verified is True
    assert verified.last_error is None


def test_verify_channel_raises_and_records_the_error_on_failure(monkeypatch):
    channel = NotificationChannelFactory(is_verified=False)
    monkeypatch.setattr(
        "apps.notifications.providers.EmailProvider.send",
        lambda self, config, *, subject, message: SendResult(
            success=False, permanent_error=True, error_message="mailbox not found"
        ),
    )

    with pytest.raises(DomainError):
        services.verify_channel(channel=channel)

    channel.refresh_from_db()
    assert channel.is_verified is False
    assert channel.last_error == "mailbox not found"
    assert channel.last_error_at is not None
