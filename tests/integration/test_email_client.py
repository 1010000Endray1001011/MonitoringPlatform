import smtplib

from integrations.email import send_email


def test_success_returns_a_successful_result_and_lands_in_the_test_outbox(mailoutbox):
    result = send_email("dev@example.com", "Subject", "Body")

    assert result.success is True
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["dev@example.com"]


def test_smtp_5xx_response_is_a_permanent_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise smtplib.SMTPResponseException(550, "Mailbox not found")

    monkeypatch.setattr("integrations.email.client.send_mail", _raise)

    result = send_email("dev@example.com", "Subject", "Body")

    assert result.success is False
    assert result.permanent_error is True


def test_smtp_4xx_response_is_a_temporary_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise smtplib.SMTPResponseException(450, "Mailbox busy")

    monkeypatch.setattr("integrations.email.client.send_mail", _raise)

    result = send_email("dev@example.com", "Subject", "Body")

    assert result.success is False
    assert result.permanent_error is False


def test_connection_level_failure_is_temporary(monkeypatch):
    def _raise(*args, **kwargs):
        raise smtplib.SMTPServerDisconnected("connection lost")

    monkeypatch.setattr("integrations.email.client.send_mail", _raise)

    result = send_email("dev@example.com", "Subject", "Body")

    assert result.success is False
    assert result.permanent_error is False


def test_os_level_connection_error_is_temporary(monkeypatch):
    def _raise(*args, **kwargs):
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr("integrations.email.client.send_mail", _raise)

    result = send_email("dev@example.com", "Subject", "Body")

    assert result.success is False
    assert result.permanent_error is False
