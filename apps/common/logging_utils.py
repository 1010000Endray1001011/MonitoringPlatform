"""
Everything needed to correlate one log line back to the HTTP request (or
lack of one, for a Celery task) that produced it, plus the JSON formatter
production uses to make those lines machine-parseable.

The request id lives in a contextvar rather than being passed explicitly
through every function call — it needs to reach logger calls anywhere deep
in the service/domain layers without every one of those functions taking
an extra parameter just to plumb it through.
"""

import json
import logging
from contextvars import ContextVar

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

# Attributes every LogRecord already has out of the box — anything else
# found on a record is something a caller passed in via `extra=`, and is
# exactly what JsonFormatter promotes into the structured output below
# (e.g. monitor_id, delivery_id).
_STANDARD_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
}


def get_request_id() -> str:
    return _request_id_ctx.get() or "-"


def bind_request_id(value: str):
    return _request_id_ctx.set(value)


def reset_request_id(token) -> None:
    _request_id_ctx.reset(token)


class RequestIDLogFilter(logging.Filter):
    """Stamps every record with the current request id (or "-" outside of
    a request, e.g. from a Celery worker) so log format strings can always
    reference %(request_id)s without risking a KeyError on records that
    would otherwise never set it."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)
