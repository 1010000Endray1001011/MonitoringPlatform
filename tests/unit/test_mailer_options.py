"""
How MAILERS["default"]["OPTIONS"] gets built from the environment.

Reaches into the private `_build_mailer_options` deliberately: the whole
point of the function is the branch it takes *before* Django ever sees the
result, and that branch is invisible from the outside once settings are
loaded. Testing through `settings.MAILERS` instead would only ever exercise
whichever backend the test settings happen to use.
"""

import environ
import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings.base import SMTP_BACKEND, _build_mailer_options

CONSOLE_BACKEND = "django.core.mail.backends.console.EmailBackend"


@pytest.mark.parametrize(
    "backend",
    [
        CONSOLE_BACKEND,
        "django.core.mail.backends.locmem.EmailBackend",
        "django.core.mail.backends.filebased.EmailBackend",
    ],
)
def test_non_smtp_backends_get_no_options(backend, monkeypatch):
    # Regression: passing SMTP options to a backend that doesn't take them
    # raises InvalidMailer("Unknown options 'host', 'port'") while settings
    # are still loading, i.e. the whole app fails to start. Development runs
    # the console backend by default, so getting this wrong breaks a fresh
    # `docker compose up` for everyone who hasn't configured SMTP.
    monkeypatch.setenv("EMAIL_HOST", "smtp.example.com")
    monkeypatch.setenv("EMAIL_PORT", "2525")

    assert _build_mailer_options(backend, environ.Env()) == {}


def test_smtp_backend_reads_every_option_from_the_environment(monkeypatch):
    monkeypatch.setenv("EMAIL_HOST", "smtp.gmail.com")
    monkeypatch.setenv("EMAIL_PORT", "587")
    monkeypatch.setenv("EMAIL_HOST_USER", "alerts@example.com")
    monkeypatch.setenv("EMAIL_HOST_PASSWORD", "app-password")
    monkeypatch.setenv("EMAIL_TIMEOUT", "7")

    options = _build_mailer_options(SMTP_BACKEND, environ.Env())

    assert options == {
        "host": "smtp.gmail.com",
        "port": 587,
        "username": "alerts@example.com",
        "password": "app-password",
        "use_ssl": False,
        "use_tls": True,
        "timeout": 7,
    }


def test_option_names_match_the_backend_signature():
    # The keys are passed as keyword arguments to the backend class, so a
    # rename on Django's side (or a typo here) has to fail loudly rather
    # than at the first attempt to send a real alert.
    import inspect

    from django.core.mail.backends.smtp import EmailBackend

    accepted = set(inspect.signature(EmailBackend.__init__).parameters)
    monkeypatched = _build_mailer_options(SMTP_BACKEND, environ.Env())

    assert set(monkeypatched) <= accepted


def test_a_timeout_is_always_set(monkeypatch):
    # Without one, a silently hung SMTP server holds the Celery worker that
    # is trying to deliver an incident notification.
    monkeypatch.delenv("EMAIL_TIMEOUT", raising=False)

    assert _build_mailer_options(SMTP_BACKEND, environ.Env())["timeout"] == 10


def test_use_ssl_alone_switches_off_starttls(monkeypatch):
    # Port 465 is implicit TLS. Setting only EMAIL_USE_SSL must not collide
    # with a use_tls that defaulted to True on its own.
    monkeypatch.setenv("EMAIL_USE_SSL", "True")
    monkeypatch.delenv("EMAIL_USE_TLS", raising=False)

    options = _build_mailer_options(SMTP_BACKEND, environ.Env())

    assert options["use_ssl"] is True
    assert options["use_tls"] is False


def test_setting_both_encryption_modes_fails_at_startup(monkeypatch):
    # Caught while settings load rather than on the first send, which would
    # otherwise surface inside a Celery task long after deployment.
    monkeypatch.setenv("EMAIL_USE_SSL", "True")
    monkeypatch.setenv("EMAIL_USE_TLS", "True")

    with pytest.raises(ImproperlyConfigured, match="mutually exclusive"):
        _build_mailer_options(SMTP_BACKEND, environ.Env())
