from apps.notifications.models import NotificationChannel
from apps.notifications.providers import EmailProvider, TelegramProvider, get_provider
from integrations.notification_result import SendResult


def test_telegram_provider_delegates_to_the_telegram_client_and_folds_subject_into_text(
    monkeypatch,
):
    calls = []

    def _fake_send_message(chat_id, text):
        calls.append((chat_id, text))
        return SendResult(success=True)

    monkeypatch.setattr("apps.notifications.providers.send_telegram_message", _fake_send_message)

    result = TelegramProvider().send({"chat_id": "123"}, subject="Down", message="details")

    assert result.success is True
    assert calls == [("123", "Down\n\ndetails")]


def test_email_provider_delegates_to_the_email_client(monkeypatch):
    calls = []

    def _fake_send_email(to_email, subject, message):
        calls.append((to_email, subject, message))
        return SendResult(success=True)

    monkeypatch.setattr("apps.notifications.providers.send_email", _fake_send_email)

    result = EmailProvider().send({"email": "a@example.com"}, subject="Down", message="details")

    assert result.success is True
    assert calls == [("a@example.com", "Down", "details")]


def test_get_provider_returns_the_matching_implementation():
    assert isinstance(get_provider(NotificationChannel.ChannelType.EMAIL), EmailProvider)
    assert isinstance(get_provider(NotificationChannel.ChannelType.TELEGRAM), TelegramProvider)


def test_email_provider_fails_permanently_on_a_config_missing_the_email_key():
    result = EmailProvider().send({}, subject="Down", message="details")

    assert result.success is False
    assert result.permanent_error is True


def test_telegram_provider_fails_permanently_on_a_config_missing_the_chat_id_key():
    result = TelegramProvider().send({}, subject="Down", message="details")

    assert result.success is False
    assert result.permanent_error is True
