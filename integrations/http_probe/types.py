"""
Types shared by every HTTP probe implementation. This module — and this
whole package — never imports a Django model. It's the seam between "what a
check measured" and "what the rest of the system does with that
measurement": everything on the far side of the seam talks in these plain
dataclasses, never in a `requests.Response` or an ORM row.
"""

from dataclasses import dataclass
from typing import Protocol

# Stable string codes for why a check failed. Duplicated as
# apps.checks.models.CheckResult.ErrorType (a Django TextChoices) on the
# storage side — a test asserts the two sets stay identical, since a silent
# drift here would just mean some outcome can never be saved correctly.
DNS_ERROR = "DNS_ERROR"
CONNECTION_REFUSED = "CONNECTION_REFUSED"
CONNECTION_ERROR = "CONNECTION_ERROR"
TIMEOUT = "TIMEOUT"
SSL_ERROR = "SSL_ERROR"
TOO_MANY_REDIRECTS = "TOO_MANY_REDIRECTS"
RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"
UNEXPECTED_STATUS = "UNEXPECTED_STATUS"
BLOCKED_TARGET = "BLOCKED_TARGET"
INTERNAL_ERROR = "INTERNAL_ERROR"

ALL_ERROR_TYPES = frozenset(
    {
        DNS_ERROR,
        CONNECTION_REFUSED,
        CONNECTION_ERROR,
        TIMEOUT,
        SSL_ERROR,
        TOO_MANY_REDIRECTS,
        RESPONSE_TOO_LARGE,
        UNEXPECTED_STATUS,
        BLOCKED_TARGET,
        INTERNAL_ERROR,
    }
)

# Every error_type except INTERNAL_ERROR is a fact about the target (or
# about policy, for BLOCKED_TARGET) — retrying would either skew the
# target's own statistics or, for BLOCKED_TARGET, attempt the exact request
# the SSRF guard just refused. INTERNAL_ERROR is the odd one out: it's the
# catch-all for "our side broke", not a measurement, so it's the only
# outcome the calling Celery task is allowed to retry.
NON_RETRYABLE_ERROR_TYPES = ALL_ERROR_TYPES - {INTERNAL_ERROR}


@dataclass(frozen=True)
class ProbeRequest:
    url: str
    method: str
    timeout_seconds: int
    expected_status: int
    headers: dict
    # Defaulted so every existing construction site — and every test that
    # only cares about status codes — keeps working unchanged; a body is
    # the exception, not the norm.
    body: str = ""


@dataclass(frozen=True)
class ProbeResult:
    success: bool
    status_code: int | None = None
    response_time_ms: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    response_size_bytes: int | None = None


class HttpProbe(Protocol):
    def probe(self, request: ProbeRequest) -> ProbeResult: ...
