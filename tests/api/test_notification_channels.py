import pytest
from rest_framework import status

from apps.notifications.models import NotificationChannel
from integrations.notification_result import SendResult
from tests.factories import NotificationChannelFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_create_email_channel(authenticated_client):
    response = authenticated_client.post(
        "/api/v1/notification-channels/",
        {"type": "EMAIL", "name": "My email", "config": {"email": "a@example.com"}},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["is_verified"] is False


def test_create_email_channel_rejects_missing_email_key(authenticated_client):
    response = authenticated_client.post(
        "/api/v1/notification-channels/",
        {"type": "EMAIL", "name": "Bad", "config": {}},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "config" in response.data["error"]["details"]


def test_create_rejects_a_config_that_does_not_match_the_type(authenticated_client):
    response = authenticated_client.post(
        "/api/v1/notification-channels/",
        {"type": "TELEGRAM", "name": "Bad", "config": {"email": "a@example.com"}},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_telegram_channel_rejects_missing_chat_id(authenticated_client):
    response = authenticated_client.post(
        "/api/v1/notification-channels/",
        {"type": "TELEGRAM", "name": "Bad", "config": {}},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "config" in response.data["error"]["details"]


def test_list_only_returns_the_caller_s_own_channels(authenticated_client, user):
    NotificationChannelFactory(user=user)
    NotificationChannelFactory(user=UserFactory())

    response = authenticated_client.get("/api/v1/notification-channels/")

    assert response.data["count"] == 1


def test_other_users_channel_is_never_visible(authenticated_client):
    other_channel = NotificationChannelFactory(user=UserFactory())

    for response in (
        authenticated_client.get(f"/api/v1/notification-channels/{other_channel.id}/"),
        authenticated_client.patch(
            f"/api/v1/notification-channels/{other_channel.id}/", {"name": "x"}, format="json"
        ),
        authenticated_client.delete(f"/api/v1/notification-channels/{other_channel.id}/"),
        authenticated_client.post(f"/api/v1/notification-channels/{other_channel.id}/verify/"),
    ):
        assert response.status_code == status.HTTP_404_NOT_FOUND


def test_changing_config_resets_is_verified(authenticated_client, user):
    channel = NotificationChannelFactory(user=user, is_verified=True)

    response = authenticated_client.patch(
        f"/api/v1/notification-channels/{channel.id}/",
        {"config": {"email": "new@example.com"}},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["is_verified"] is False


def test_verify_succeeds_and_marks_the_channel_verified(authenticated_client, user, monkeypatch):
    channel = NotificationChannelFactory(user=user, is_verified=False)
    monkeypatch.setattr(
        "apps.notifications.providers.EmailProvider.send",
        lambda self, config, *, subject, message: SendResult(success=True),
    )

    response = authenticated_client.post(f"/api/v1/notification-channels/{channel.id}/verify/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["is_verified"] is True


def test_verify_failure_returns_400_and_does_not_verify(authenticated_client, user, monkeypatch):
    channel = NotificationChannelFactory(user=user, is_verified=False)
    monkeypatch.setattr(
        "apps.notifications.providers.EmailProvider.send",
        lambda self, config, *, subject, message: SendResult(
            success=False, permanent_error=True, error_message="bounced"
        ),
    )

    response = authenticated_client.post(f"/api/v1/notification-channels/{channel.id}/verify/")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    channel.refresh_from_db()
    assert channel.is_verified is False


def test_delete_channel(authenticated_client, user):
    channel = NotificationChannelFactory(user=user)

    response = authenticated_client.delete(f"/api/v1/notification-channels/{channel.id}/")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not NotificationChannel.objects.filter(id=channel.id).exists()


def test_unauthenticated_request_is_rejected(api_client):
    response = api_client.get("/api/v1/notification-channels/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
