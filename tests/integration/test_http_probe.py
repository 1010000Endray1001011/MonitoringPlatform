"""
RequestsHttpProbe against mocked HTTP responses — no real network calls, no
real socket connections. `responses` patches at the same layer `requests`
itself uses to send a request, so these exercise the actual HTTP handling
code, not a stand-in for it.

Every target here is 127.0.0.1: `MONITORING_ALLOW_PRIVATE_TARGETS` defaults
to True in test settings, so the SSRF pre-check lets it through without
needing DNS at all — resolving a literal IP is instant and needs no
network access either way.
"""

import requests as requests_lib
import responses

from integrations.http_probe import ProbeRequest
from integrations.http_probe.requests_probe import RequestsHttpProbe
from integrations.http_probe.types import (
    BLOCKED_TARGET,
    CONNECTION_ERROR,
    INTERNAL_ERROR,
    RESPONSE_TOO_LARGE,
    SSL_ERROR,
    TIMEOUT,
    UNEXPECTED_STATUS,
)

TARGET_URL = "http://127.0.0.1/"


def _request(**overrides) -> ProbeRequest:
    defaults = dict(
        url=TARGET_URL, method="GET", timeout_seconds=5, expected_status=200, headers={}
    )
    defaults.update(overrides)
    return ProbeRequest(**defaults)


@responses.activate
def test_successful_probe_matches_expected_status():
    responses.add(responses.GET, TARGET_URL, status=200, body="ok")

    result = RequestsHttpProbe().probe(_request())

    assert result.success is True
    assert result.status_code == 200
    assert result.error_type is None
    assert result.response_time_ms is not None
    assert result.response_size_bytes == 2


@responses.activate
def test_unexpected_status_is_recorded_as_a_failed_but_real_measurement():
    responses.add(responses.GET, TARGET_URL, status=503)

    result = RequestsHttpProbe().probe(_request(expected_status=200))

    assert result.success is False
    assert result.status_code == 503
    assert result.error_type == UNEXPECTED_STATUS


@responses.activate
def test_timeout_is_classified_as_timeout():
    responses.add(responses.GET, TARGET_URL, body=requests_lib.exceptions.ConnectTimeout())

    result = RequestsHttpProbe().probe(_request())

    assert result.success is False
    assert result.status_code is None
    assert result.error_type == TIMEOUT


@responses.activate
def test_ssl_error_is_classified_as_ssl_error():
    responses.add(
        responses.GET, TARGET_URL, body=requests_lib.exceptions.SSLError("bad certificate")
    )

    result = RequestsHttpProbe().probe(_request())

    assert result.error_type == SSL_ERROR


@responses.activate
def test_generic_connection_error_falls_back_to_connection_error():
    responses.add(responses.GET, TARGET_URL, body=requests_lib.exceptions.ConnectionError("boom"))

    result = RequestsHttpProbe().probe(_request())

    assert result.error_type == CONNECTION_ERROR


@responses.activate
def test_unanticipated_exception_is_classified_as_internal_error():
    # Nothing about this is a fact about the target — it's the catch-all
    # for a bug or an environment problem on our own side, and the only
    # error_type the calling Celery task is allowed to retry because of it.
    responses.add(responses.GET, TARGET_URL, body=ValueError("unexpected bug"))

    result = RequestsHttpProbe().probe(_request())

    assert result.error_type == INTERNAL_ERROR


@responses.activate
def test_response_larger_than_the_configured_limit_is_rejected(settings):
    settings.MONITORING_MAX_RESPONSE_BYTES = 10
    responses.add(responses.GET, TARGET_URL, status=200, body="x" * 100)

    result = RequestsHttpProbe().probe(_request())

    assert result.success is False
    assert result.error_type == RESPONSE_TOO_LARGE
    # The response did start — status_code is still known even though the
    # body was cut off partway through.
    assert result.status_code == 200


def test_blocked_target_never_reaches_the_network(settings):
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False
    # Deliberately no `responses.activate` / `responses.add` here: if the
    # SSRF guard failed to short-circuit, this would fall through to a real
    # `requests` call against an unmocked URL and raise on its own —
    # proving the guard failed rather than silently passing.
    result = RequestsHttpProbe().probe(_request())

    assert result.success is False
    assert result.error_type == BLOCKED_TARGET
