import json
import logging

from apps.common.logging_utils import (
    JsonFormatter,
    RequestIDLogFilter,
    bind_request_id,
    get_request_id,
    reset_request_id,
)


def _make_record(**extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="apps.checks.tasks",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="check completed",
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_get_request_id_defaults_to_a_placeholder_outside_any_request():
    assert get_request_id() == "-"


def test_bind_and_reset_request_id_round_trip():
    token = bind_request_id("abc123")
    assert get_request_id() == "abc123"
    reset_request_id(token)
    assert get_request_id() == "-"


def test_request_id_log_filter_stamps_the_current_id():
    token = bind_request_id("xyz789")
    try:
        record = _make_record()
        assert RequestIDLogFilter().filter(record) is True
        assert record.request_id == "xyz789"
    finally:
        reset_request_id(token)


def test_json_formatter_includes_extra_fields():
    record = _make_record(request_id="abc123", monitor_id="m-1", success=True)

    output = json.loads(JsonFormatter().format(record))

    assert output["message"] == "check completed"
    assert output["level"] == "INFO"
    assert output["request_id"] == "abc123"
    assert output["monitor_id"] == "m-1"
    assert output["success"] is True


def test_json_formatter_defaults_request_id_when_missing():
    record = _make_record()

    output = json.loads(JsonFormatter().format(record))

    assert output["request_id"] == "-"
