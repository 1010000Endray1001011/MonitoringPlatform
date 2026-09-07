"""
The real HttpProbe implementation, backed by the `requests` library.

Every exception `requests` can raise is caught here and turned into a
ProbeResult instead of propagating — a failed probe is a *measurement*
("the target didn't respond in time"), not an error in the calling task.
That distinction is what lets the rest of the system treat "the target is
down" and "our code crashed" completely differently: one is history worth
keeping exactly as it happened, the other is worth retrying.
"""

import socket
import time

import requests
from django.conf import settings

from .ssrf_guard import check_target_is_allowed
from .types import (
    CONNECTION_ERROR,
    CONNECTION_REFUSED,
    DNS_ERROR,
    INTERNAL_ERROR,
    RESPONSE_TOO_LARGE,
    SSL_ERROR,
    TIMEOUT,
    UNEXPECTED_STATUS,
    ProbeRequest,
    ProbeResult,
)

# A short, fixed cap on the TCP-connect phase, independent of the monitor's
# own timeout_seconds — a target that never completes its handshake
# shouldn't be able to hold a worker for the full read timeout on top of
# that. `requests`' (connect, read) timeout tuple isn't additive — each
# phase gets its own allowance — so worst-case wall time here is
# CONNECT_TIMEOUT_SECONDS + timeout_seconds, not timeout_seconds alone.
# That looseness is accepted rather than enforcing a hard wall-clock
# deadline with threads or signals, which would be a lot of machinery for
# a bound that's already reasonable in practice.
CONNECT_TIMEOUT_SECONDS = 5


class _ResponseTooLarge(Exception):
    pass


def _classify_connection_error(exc: BaseException) -> str:
    # `requests`/urllib3 wrap the actual low-level failure several layers
    # deep instead of raising it directly, so the real cause has to be
    # found by walking the exception chain rather than by inspecting `exc`
    # itself. Falling back to CONNECTION_ERROR for anything unrecognised
    # keeps this from ever raising on its own.
    cause: BaseException | None = exc
    while cause is not None:
        if isinstance(cause, socket.gaierror):
            return DNS_ERROR
        if isinstance(cause, ConnectionRefusedError):
            return CONNECTION_REFUSED
        cause = cause.__cause__ or cause.__context__
    return CONNECTION_ERROR


# Sending a body with no Content-Type leaves the target guessing, and most
# APIs answer that guess with a 415 — which would look like a failing
# monitor rather than a misconfigured one. JSON is the overwhelmingly
# common case for the health endpoints this feature exists for, so it's the
# default when a body is present and the user didn't say otherwise.
#
# Only a default: an explicit Content-Type in the monitor's own headers
# always wins, and the lookup is case-insensitive because header names are
# (a user typing "content-type" must not end up sending two of them).
DEFAULT_BODY_CONTENT_TYPE = "application/json"


def _headers_with_content_type(request: ProbeRequest) -> dict:
    headers = dict(request.headers)
    if not request.body:
        return headers
    if any(name.lower() == "content-type" for name in headers):
        return headers
    headers["Content-Type"] = DEFAULT_BODY_CONTENT_TYPE
    return headers


class RequestsHttpProbe:
    def probe(self, request: ProbeRequest) -> ProbeResult:
        parsed = requests.utils.urlparse(request.url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        blocked_error_type = check_target_is_allowed(parsed.hostname, port)
        if blocked_error_type is not None:
            return ProbeResult(
                success=False,
                error_type=blocked_error_type,
                error_message=f"Target resolves to a disallowed address: {parsed.hostname}",
            )

        started_at = time.monotonic()
        try:
            response = requests.request(
                request.method,
                request.url,
                headers=_headers_with_content_type(request),
                # Encoded here rather than handed over as a str: `requests`
                # would otherwise pick an encoding itself, and a body that
                # travels as latin-1 when the target expects UTF-8 fails in
                # a way that looks like the target's fault. None (not b"")
                # when there's no body, so a GET keeps sending no
                # Content-Length at all.
                data=request.body.encode("utf-8") if request.body else None,
                timeout=(CONNECT_TIMEOUT_SECONDS, request.timeout_seconds),
                # Following a redirect would mean connecting to a second
                # URL that never went through either half of the SSRF
                # guard — treating a 3xx as a normal response and letting
                # expected_status decide is the safe behaviour for now.
                allow_redirects=False,
                stream=True,
            )
        except requests.exceptions.SSLError as exc:
            return ProbeResult(success=False, error_type=SSL_ERROR, error_message=str(exc))
        except (
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ReadTimeout,
            requests.exceptions.Timeout,
        ) as exc:
            return ProbeResult(success=False, error_type=TIMEOUT, error_message=str(exc))
        except requests.exceptions.ConnectionError as exc:
            return ProbeResult(
                success=False, error_type=_classify_connection_error(exc), error_message=str(exc)
            )
        except Exception as exc:  # noqa: BLE001 — deliberate catch-all, see module docstring
            # Anything not explicitly handled above is our own fault, not a
            # fact about the target — an unexpected bug, a resource limit,
            # anything we didn't anticipate. This is the only outcome the
            # calling task is allowed to retry.
            return ProbeResult(success=False, error_type=INTERNAL_ERROR, error_message=str(exc))

        try:
            body_size = self._read_capped(response)
        except _ResponseTooLarge:
            response.close()
            return ProbeResult(
                success=False,
                error_type=RESPONSE_TOO_LARGE,
                status_code=response.status_code,
                response_time_ms=self._elapsed_ms(started_at),
            )

        response_time_ms = self._elapsed_ms(started_at)
        success = response.status_code == request.expected_status
        return ProbeResult(
            success=success,
            status_code=response.status_code,
            response_time_ms=response_time_ms,
            error_type=None if success else UNEXPECTED_STATUS,
            response_size_bytes=body_size,
        )

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return int((time.monotonic() - started_at) * 1000)

    @staticmethod
    def _read_capped(response: requests.Response) -> int:
        # Read with a hard ceiling instead of trusting Content-Length (which
        # can be absent, wrong, or omitted deliberately) — a target that
        # streams an unbounded body shouldn't be able to exhaust a worker's
        # memory just because it was configured as a monitor.
        limit = settings.MONITORING_MAX_RESPONSE_BYTES
        total = 0
        for chunk in response.iter_content(chunk_size=8192):
            total += len(chunk)
            if total > limit:
                raise _ResponseTooLarge
        return total
