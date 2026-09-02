from unittest.mock import MagicMock

import pytest
from rest_framework.throttling import SimpleRateThrottle

from apps.common.throttling import (
    FailOpenAnonRateThrottle,
    FailOpenScopedRateThrottle,
    FailOpenUserRateThrottle,
)


class _BrokenCache:
    """Stands in for a cache backend that can't reach Redis."""

    def get(self, *args, **kwargs):
        raise ConnectionError("Redis is unreachable.")

    def set(self, *args, **kwargs):
        raise ConnectionError("Redis is unreachable.")


@pytest.fixture(autouse=True)
def _broken_cache_backend(monkeypatch):
    # SimpleRateThrottle.cache is a class attribute shared by every
    # subclass (Anon/User/Scoped) — patching it here breaks the cache for
    # all three at once, exactly like a real Redis outage would.
    monkeypatch.setattr(SimpleRateThrottle, "cache", _BrokenCache())


@pytest.mark.parametrize(
    "throttle_class,scope",
    [
        (FailOpenAnonRateThrottle, None),
        (FailOpenUserRateThrottle, None),
        (FailOpenScopedRateThrottle, "monitor_check"),
    ],
)
def test_allow_request_fails_open_when_the_cache_backend_is_unreachable(throttle_class, scope):
    throttle = throttle_class()
    if scope is not None:
        throttle.scope = scope
        throttle.rate = throttle.get_rate()
        throttle.num_requests, throttle.duration = throttle.parse_rate(throttle.rate)

    request = MagicMock()
    request.META = {}
    request.user = MagicMock(pk=1)
    request.user.is_authenticated = True

    assert throttle.allow_request(request, view=MagicMock()) is True
