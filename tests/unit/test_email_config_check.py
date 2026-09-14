"""
The startup warning for SMTP details left next to a non-SMTP backend.

This is the one email misconfiguration nothing downstream can detect: the
console backend reports a successful send, so the delivery is recorded as
SENT and the only symptom is a message that never arrives.
"""

from apps.notifications.system_checks import smtp_details_without_the_smtp_backend

CONSOLE_BACKEND = "django.core.mail.backends.console.EmailBackend"


def _run(settings, monkeypatch, *, backend, env):
    settings.MAILERS = {"default": {"BACKEND": backend, "OPTIONS": {}}}
    for name in ("EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return smtp_details_without_the_smtp_backend(app_configs=None)


def test_warns_when_credentials_are_set_but_the_backend_still_prints(settings, monkeypatch):
    warnings = _run(
        settings,
        monkeypatch,
        backend=CONSOLE_BACKEND,
        env={"EMAIL_HOST_USER": "someone@gmail.com", "EMAIL_HOST_PASSWORD": "app-password"},
    )

    assert [w.id for w in warnings] == ["notifications.W001"]
    # The hint has to carry the fix itself: whoever sees this is already
    # looking for why mail vanished, not reading the docs from the top.
    assert "smtp.EmailBackend" in warnings[0].hint


def test_silent_on_a_fresh_clone_that_never_configured_smtp(settings, monkeypatch):
    # The default setup — console backend, no credentials — is a legitimate
    # choice, not a half-finished one. Warning here would train people to
    # ignore the check.
    assert _run(settings, monkeypatch, backend=CONSOLE_BACKEND, env={}) == []


def test_silent_once_the_smtp_backend_is_selected(settings, monkeypatch):
    assert (
        _run(
            settings,
            monkeypatch,
            backend=settings.SMTP_BACKEND,
            env={"EMAIL_HOST_USER": "someone@gmail.com"},
        )
        == []
    )
