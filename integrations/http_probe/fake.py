"""
A deterministic stand-in for RequestsHttpProbe.

Service and task tests that need to drive apps.checks.processor shouldn't
have to make real network calls or mock `requests` just to get a known
ProbeResult back — real HTTP behaviour (timeouts, TLS, redirects, byte
limits) is covered on its own, against mocked HTTP responses, next to
RequestsHttpProbe itself. This fake exists purely so the rest of the system
can be tested against a fixed, instant outcome.
"""

from .types import ProbeRequest, ProbeResult


class FakeHttpProbe:
    def __init__(self, result: ProbeResult | None = None):
        self.result = result or ProbeResult(success=True, status_code=200, response_time_ms=10)
        self.calls: list[ProbeRequest] = []

    def probe(self, request: ProbeRequest) -> ProbeResult:
        self.calls.append(request)
        return self.result
