"""
DRF's built-in throttle classes call straight into the cache backend
(`self.cache.get(...)` / `self.cache.set(...)`) with no error handling of
their own. In this project the cache backend is Redis in every real
environment (see CACHES in settings) — if Redis is down, every single
request would start raising a raw connection error out of `allow_request`
and turn into a 500, even though rate limiting failing is not something a
caller did wrong and is not worth taking the whole API down for. A
monitoring platform going fully unavailable because its own rate limiter's
dependency died is a worse outcome than temporarily not rate limiting at
all, so every throttle class used by this project fails *open*: if the
cache backend errors out, the request is allowed through and the failure is
logged instead of raised.
"""

import logging

from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle, UserRateThrottle

logger = logging.getLogger(__name__)


class FailOpenThrottleMixin:
    def allow_request(self, request, view) -> bool:
        try:
            return super().allow_request(request, view)
        except Exception:
            logger.warning(
                "Rate limiting backend unavailable; allowing request through unthrottled.",
                exc_info=True,
            )
            return True


class FailOpenAnonRateThrottle(FailOpenThrottleMixin, AnonRateThrottle):
    pass


class FailOpenUserRateThrottle(FailOpenThrottleMixin, UserRateThrottle):
    pass


class FailOpenScopedRateThrottle(FailOpenThrottleMixin, ScopedRateThrottle):
    pass
