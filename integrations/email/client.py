"""
Thin wrapper over Django's own email backend. The backend itself (console
in dev, SMTP in production — see MAILERS in settings) is Django's problem;
this module's only job is turning whatever it raises into the same
SendResult shape integrations.telegram already returns, so
apps.notifications doesn't need to know which provider it's talking to.
"""

import smtplib

from django.conf import settings
from django.core.mail import send_mail

from integrations.notification_result import SendResult


def send_email(to_email: str, subject: str, message: str) -> SendResult:
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [to_email], fail_silently=False)
    except smtplib.SMTPResponseException as exc:
        # SMTP status codes follow the same 4xx/5xx convention as HTTP:
        # 5xx means the server has permanently rejected this recipient or
        # message, 4xx means try again later (a full mailbox, a greylist).
        permanent = exc.smtp_code >= 500
        return SendResult(success=False, permanent_error=permanent, error_message=str(exc))
    except smtplib.SMTPException as exc:
        return SendResult(success=False, error_message=str(exc))
    except OSError as exc:
        # Connection-level failure (DNS, refused, timed out) reaching the
        # SMTP server itself — nothing here says the address is bad.
        return SendResult(success=False, error_message=str(exc))

    return SendResult(success=True)
