import responses

from integrations.telegram import send_message

TOKEN = "test-bot-token"
URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"


@responses.activate
def test_success_returns_a_successful_result(settings):
    settings.TELEGRAM_BOT_TOKEN = TOKEN
    responses.add(responses.POST, URL, json={"ok": True, "result": {}}, status=200)

    result = send_message("123", "hello")

    assert result.success is True


@responses.activate
def test_bad_chat_id_is_a_permanent_error(settings):
    settings.TELEGRAM_BOT_TOKEN = TOKEN
    responses.add(
        responses.POST,
        URL,
        json={"ok": False, "description": "Bad Request: chat not found"},
        status=400,
    )

    result = send_message("bogus", "hello")

    assert result.success is False
    assert result.permanent_error is True
    assert "chat not found" in result.error_message


@responses.activate
def test_rate_limiting_is_temporary_and_carries_retry_after(settings):
    settings.TELEGRAM_BOT_TOKEN = TOKEN
    responses.add(
        responses.POST,
        URL,
        json={
            "ok": False,
            "description": "Too Many Requests: retry later",
            "parameters": {"retry_after": 30},
        },
        status=429,
    )

    result = send_message("123", "hello")

    assert result.success is False
    assert result.permanent_error is False
    assert result.retry_after == 30


@responses.activate
def test_server_error_is_temporary(settings):
    settings.TELEGRAM_BOT_TOKEN = TOKEN
    responses.add(responses.POST, URL, json={"ok": False}, status=500)

    result = send_message("123", "hello")

    assert result.success is False
    assert result.permanent_error is False


@responses.activate
def test_network_failure_is_temporary(settings):
    import requests as requests_lib

    settings.TELEGRAM_BOT_TOKEN = TOKEN
    responses.add(responses.POST, URL, body=requests_lib.exceptions.ConnectionError("boom"))

    result = send_message("123", "hello")

    assert result.success is False
    assert result.permanent_error is False


@responses.activate
def test_a_non_json_error_body_still_produces_a_usable_message(settings):
    settings.TELEGRAM_BOT_TOKEN = TOKEN
    responses.add(responses.POST, URL, body="<html>Bad Gateway</html>", status=502)

    result = send_message("123", "hello")

    assert result.success is False
    assert result.permanent_error is False
    assert "Bad Gateway" in result.error_message


def test_missing_bot_token_is_a_permanent_error(settings):
    settings.TELEGRAM_BOT_TOKEN = ""

    result = send_message("123", "hello")

    assert result.success is False
    assert result.permanent_error is True
