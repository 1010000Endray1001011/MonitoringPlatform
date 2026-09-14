"""
The connect handshake: issuing a one-time link and resolving the /start
that comes back.

This is the only place a Telegram chat_id is ever assigned, so these tests
carry the security-relevant cases too — a link must not be usable by the
wrong account, and must not be usable twice by different chats.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.notifications import services
from apps.notifications.models import NotificationChannel, TelegramClaim
from tests.factories import NotificationChannelFactory, UserFactory

pytestmark = pytest.mark.django_db


def make_telegram_channel(**config) -> NotificationChannel:
    # The factory writes straight to the ORM, bypassing create_channel and
    # therefore the claim it would have issued — so issue one here. Tests
    # that care about the service doing it on its own call create_channel.
    channel = NotificationChannelFactory(
        type=NotificationChannel.ChannelType.TELEGRAM,
        config=config,
        is_verified=False,
    )
    services.issue_telegram_claim(channel=channel)
    return channel


def test_creating_a_telegram_channel_issues_a_link_immediately():
    # The channel is useless without one, so asking for it separately would
    # only be a step every caller has to remember.
    channel = services.create_channel(
        user=UserFactory(),
        type=NotificationChannel.ChannelType.TELEGRAM,
        name="My phone",
        config={"username": "someone"},
    )

    assert TelegramClaim.objects.filter(channel=channel).exists()


def test_creating_an_email_channel_issues_no_link():
    channel = services.create_channel(
        user=UserFactory(),
        type=NotificationChannel.ChannelType.EMAIL,
        name="Inbox",
        config={"email": "a@example.com"},
    )

    assert not TelegramClaim.objects.filter(channel=channel).exists()


def test_a_matching_start_binds_the_chat_and_verifies_the_channel():
    channel = make_telegram_channel(username="someone")
    claim = channel.telegram_claim

    outcome = services.claim_telegram_chat(token=claim.token, chat_id="98765", username="someone")

    channel.refresh_from_db()
    assert outcome.linked is True
    assert channel.config["chat_id"] == "98765"
    assert channel.is_verified is True
    claim.refresh_from_db()
    assert claim.claimed_at is not None


def test_username_comparison_ignores_case_and_a_leading_at():
    channel = make_telegram_channel(username="@SomeOne")

    outcome = services.claim_telegram_chat(
        token=channel.telegram_claim.token, chat_id="1", username="someone"
    )

    assert outcome.linked is True


def test_a_different_account_cannot_use_someone_elses_link():
    # The whole point of declaring a username: "I said @me, so I get @me".
    channel = make_telegram_channel(username="someone")

    outcome = services.claim_telegram_chat(
        token=channel.telegram_claim.token, chat_id="1", username="someone_else"
    )

    channel.refresh_from_db()
    assert outcome.linked is False
    assert "chat_id" not in channel.config
    assert channel.is_verified is False


def test_a_channel_with_no_declared_username_binds_whoever_opens_the_link():
    # Telegram accounts aren't obliged to have a username at all. The token
    # is unguessable and only ever shown to the channel's owner, so it is
    # the identity here; the username is a cross-check when one was given.
    channel = make_telegram_channel()

    outcome = services.claim_telegram_chat(
        token=channel.telegram_claim.token, chat_id="42", username=None
    )

    channel.refresh_from_db()
    assert outcome.linked is True
    assert channel.config["chat_id"] == "42"


def test_an_expired_link_binds_nothing():
    channel = make_telegram_channel(username="someone")
    claim = channel.telegram_claim
    claim.expires_at = timezone.now() - timedelta(seconds=1)
    claim.save(update_fields=["expires_at"])

    outcome = services.claim_telegram_chat(token=claim.token, chat_id="1", username="someone")

    channel.refresh_from_db()
    assert outcome.linked is False
    assert "expired" in outcome.reply.lower()
    assert channel.is_verified is False


def test_an_unknown_token_binds_nothing():
    outcome = services.claim_telegram_chat(token="not-a-real-token", chat_id="1", username="x")

    assert outcome.linked is False


def test_tapping_the_same_link_twice_from_the_same_chat_is_idempotent():
    # Matters beyond politeness: if the offset cache is ever lost, Telegram
    # re-sends up to 24h of updates and every one of them is replayed.
    channel = make_telegram_channel(username="someone")
    token = channel.telegram_claim.token
    services.claim_telegram_chat(token=token, chat_id="55", username="someone")

    outcome = services.claim_telegram_chat(token=token, chat_id="55", username="someone")

    channel.refresh_from_db()
    assert outcome.linked is False
    assert "already connected" in outcome.reply.lower()
    assert channel.config["chat_id"] == "55"


def test_a_used_link_cannot_be_redirected_to_another_chat():
    channel = make_telegram_channel(username="someone")
    token = channel.telegram_claim.token
    services.claim_telegram_chat(token=token, chat_id="55", username="someone")

    outcome = services.claim_telegram_chat(token=token, chat_id="66", username="someone")

    channel.refresh_from_db()
    assert outcome.linked is False
    assert channel.config["chat_id"] == "55"


def test_issuing_a_new_link_invalidates_the_previous_one():
    channel = make_telegram_channel(username="someone")
    old_token = channel.telegram_claim.token

    services.issue_telegram_claim(channel=channel)

    outcome = services.claim_telegram_chat(token=old_token, chat_id="1", username="someone")
    assert outcome.linked is False
    assert TelegramClaim.objects.filter(channel=channel).count() == 1


def test_deep_link_is_built_from_the_configured_bot_username(settings):
    settings.TELEGRAM_BOT_USERNAME = "m0nit0ring_api_bot"
    channel = make_telegram_channel(username="someone")

    link = services.telegram_deep_link(channel=channel)

    assert link == f"https://t.me/m0nit0ring_api_bot?start={channel.telegram_claim.token}"


def test_deep_link_drops_an_at_sign_pasted_into_the_bot_username(settings):
    # "@name" is how Telegram itself displays a handle, so it is what gets
    # pasted into .env — but "t.me/@name" is not a valid t.me path. Telegram
    # redirects it to its download page and loses the ?start payload, so the
    # link looks broken and the chat is never bound. Cheap to tolerate here.
    settings.TELEGRAM_BOT_USERNAME = "@m0nit0ring_api_bot"
    channel = make_telegram_channel(username="someone")

    link = services.telegram_deep_link(channel=channel)

    assert link == f"https://t.me/m0nit0ring_api_bot?start={channel.telegram_claim.token}"


def test_no_deep_link_once_the_channel_is_connected(settings):
    settings.TELEGRAM_BOT_USERNAME = "m0nit0ring_api_bot"
    channel = make_telegram_channel(username="someone")
    services.claim_telegram_chat(
        token=channel.telegram_claim.token, chat_id="1", username="someone"
    )
    channel.refresh_from_db()

    assert services.telegram_deep_link(channel=channel) is None


@pytest.mark.parametrize("configured", ["", "   ", "@"])
def test_no_deep_link_without_a_configured_bot_username(settings, configured):
    # "@" on its own is what an operator leaves behind after deleting the name
    # but not the sigil; it normalises to empty, which is no username at all.
    settings.TELEGRAM_BOT_USERNAME = configured
    channel = make_telegram_channel(username="someone")

    assert services.telegram_deep_link(channel=channel) is None


def test_verify_refuses_an_unconnected_telegram_channel():
    from apps.common.exceptions import ConflictError

    channel = make_telegram_channel(username="someone")

    with pytest.raises(ConflictError):
        services.verify_channel(channel=channel)
