"""
The polling task: what it asks Telegram for, and what it does with the
answer. The Telegram client is stubbed throughout — these are about the
task's own decisions (locking, acknowledging, dispatching), not about HTTP.
"""

import pytest
from django.core.cache import cache

from apps.notifications import tasks
from apps.notifications.models import NotificationChannel
from apps.notifications.services import issue_telegram_claim
from integrations.telegram.client import UpdatesResult
from tests.factories import NotificationChannelFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_poll_state(settings):
    settings.TELEGRAM_BOT_TOKEN = "test-token"
    cache.delete(tasks.POLL_LOCK_KEY)
    cache.delete(tasks.POLL_OFFSET_KEY)
    yield
    cache.delete(tasks.POLL_LOCK_KEY)
    cache.delete(tasks.POLL_OFFSET_KEY)


def start_update(update_id: int, *, payload: str, chat_id=555, username="someone") -> dict:
    text = f"/start {payload}".strip()
    return {
        "update_id": update_id,
        "message": {
            "text": text,
            "chat": {"id": chat_id},
            "from": {"username": username},
        },
    }


def stub_telegram(monkeypatch, result: UpdatesResult):
    sent: list[tuple] = []
    calls: list[dict] = []

    def fake_get_updates(*, offset=None, timeout=0):
        calls.append({"offset": offset, "timeout": timeout})
        return result

    monkeypatch.setattr(tasks.telegram, "get_updates", fake_get_updates)
    monkeypatch.setattr(
        tasks.telegram, "send_message", lambda chat, text: sent.append((chat, text))
    )
    return calls, sent


def test_does_nothing_without_a_configured_token(settings, monkeypatch):
    settings.TELEGRAM_BOT_TOKEN = ""
    calls, _ = stub_telegram(monkeypatch, UpdatesResult(ok=True))

    tasks.poll_telegram_updates()

    assert calls == []


def test_a_start_with_a_valid_token_connects_the_channel(monkeypatch):
    channel = NotificationChannelFactory(
        type=NotificationChannel.ChannelType.TELEGRAM,
        config={"username": "someone"},
        is_verified=False,
    )
    claim = issue_telegram_claim(channel=channel)
    _, sent = stub_telegram(
        monkeypatch,
        UpdatesResult(ok=True, updates=[start_update(1, payload=claim.token)]),
    )

    tasks.poll_telegram_updates()

    channel.refresh_from_db()
    assert channel.config["chat_id"] == "555"
    assert channel.is_verified is True
    assert len(sent) == 1  # the bot always answers the person waiting in the chat


def test_the_offset_advances_past_handled_updates(monkeypatch):
    stub_telegram(
        monkeypatch,
        UpdatesResult(ok=True, updates=[start_update(7, payload=""), start_update(9, payload="")]),
    )

    tasks.poll_telegram_updates()

    # offset = last handled + 1 is Telegram's acknowledgement: without it
    # the same updates come back forever.
    assert cache.get(tasks.POLL_OFFSET_KEY) == 10


def test_the_stored_offset_is_sent_on_the_next_poll(monkeypatch):
    cache.set(tasks.POLL_OFFSET_KEY, 42, timeout=None)
    calls, _ = stub_telegram(monkeypatch, UpdatesResult(ok=True))

    tasks.poll_telegram_updates()

    assert calls[0]["offset"] == 42
    assert calls[0]["timeout"] == tasks.LONG_POLL_SECONDS


def test_an_api_failure_leaves_the_offset_untouched(monkeypatch):
    cache.set(tasks.POLL_OFFSET_KEY, 42, timeout=None)
    stub_telegram(
        monkeypatch, UpdatesResult(ok=False, error_message="Conflict: webhook is active")
    )

    tasks.poll_telegram_updates()

    # Advancing here would silently discard whatever we failed to fetch.
    assert cache.get(tasks.POLL_OFFSET_KEY) == 42


def test_a_held_lock_makes_the_task_a_no_op(monkeypatch):
    # Telegram serves exactly one getUpdates consumer and answers a second
    # concurrent call with 409, so overlapping runs must not both poll.
    cache.add(tasks.POLL_LOCK_KEY, "1", timeout=60)
    calls, _ = stub_telegram(monkeypatch, UpdatesResult(ok=True))

    tasks.poll_telegram_updates()

    assert calls == []


def test_the_lock_is_released_even_when_the_call_fails(monkeypatch):
    def blow_up(*, offset=None, timeout=0):
        raise RuntimeError("boom")

    monkeypatch.setattr(tasks.telegram, "get_updates", blow_up)

    with pytest.raises(RuntimeError):
        tasks.poll_telegram_updates()

    # A lock left behind would freeze the handshake for its whole TTL.
    assert cache.get(tasks.POLL_LOCK_KEY) is None


def test_a_bare_start_replies_with_instructions(monkeypatch):
    _, sent = stub_telegram(
        monkeypatch, UpdatesResult(ok=True, updates=[start_update(1, payload="")])
    )

    tasks.poll_telegram_updates()

    assert len(sent) == 1
    assert "channels page" in sent[0][1].lower()


@pytest.mark.parametrize(
    "update",
    [
        pytest.param({"update_id": 1}, id="no-message"),
        pytest.param(
            {"update_id": 1, "message": {"text": "hello", "chat": {"id": 1}}}, id="not-a-command"
        ),
        pytest.param({"update_id": 1, "message": {"text": "/start x"}}, id="no-chat"),
    ],
)
def test_updates_that_are_not_start_commands_are_ignored(monkeypatch, update):
    _, sent = stub_telegram(monkeypatch, UpdatesResult(ok=True, updates=[update]))

    tasks.poll_telegram_updates()

    assert sent == []
