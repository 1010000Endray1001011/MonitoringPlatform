"""
Public surface of the HTTP probe package.

`apps.checks.tasks.run_check` imports `get_http_probe` rather than
`RequestsHttpProbe` directly, so tests can swap in FakeHttpProbe by
monkeypatching this one function instead of reaching into `requests` itself.
"""

from .fake import FakeHttpProbe
from .requests_probe import RequestsHttpProbe
from .types import HttpProbe, ProbeRequest, ProbeResult

_default_probe: HttpProbe = RequestsHttpProbe()


def get_http_probe() -> HttpProbe:
    return _default_probe


__all__ = [
    "HttpProbe",
    "ProbeRequest",
    "ProbeResult",
    "RequestsHttpProbe",
    "FakeHttpProbe",
    "get_http_probe",
]
