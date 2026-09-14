"""
Startup checks for notification delivery configuration.

Named system_checks rather than checks so it isn't mistaken for the
apps.checks app, which is about monitoring checks and unrelated to this.

Email is the one delivery channel that can be fully configured and still
send nothing. The console backend accepts every message, prints it, and
reports success, so neither the sending code nor the outbox can tell that
apart from a real delivery — NotificationDelivery is marked SENT either
way. The mistake only ever surfaces as "the alert never arrived", which
looks identical to a dozen unrelated causes, so it is worth catching at
startup against what the operator's own configuration says they wanted.
"""

import os

from django.conf import settings
from django.core.checks import Warning as CheckWarning
from django.core.checks import register

# Variables nobody sets unless they mean to send real mail. They are
# meaningless to every backend except SMTP, so finding them next to a
# non-SMTP backend means a switch that was only half thrown, not a
# deliberate combination.
SMTP_INTENT_VARS = ("EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD")


@register()
def smtp_details_without_the_smtp_backend(app_configs, **kwargs):
    backend = settings.MAILERS["default"]["BACKEND"]
    if backend == settings.SMTP_BACKEND:
        return []

    # Read the environment rather than settings: the connection options are
    # deliberately dropped for non-SMTP backends (see _build_mailer_options),
    # so by the time this runs, settings no longer remember that they were
    # ever supplied. The environment is the only remaining evidence of intent.
    supplied = [name for name in SMTP_INTENT_VARS if os.environ.get(name)]
    if not supplied:
        return []

    return [
        CheckWarning(
            f"{' and '.join(supplied)} set, but EMAIL_BACKEND is {backend!r}, "
            "which prints email to the log instead of sending it. Email "
            "notifications will appear to succeed and never arrive.",
            hint=(
                "Set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend "
                "to deliver mail, or clear the EMAIL_HOST_* variables if "
                "printing to the log is what you want."
            ),
            id="notifications.W001",
        )
    ]
