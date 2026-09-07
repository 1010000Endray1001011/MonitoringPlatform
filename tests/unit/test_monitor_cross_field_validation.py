"""
`timeout_seconds < interval_seconds` is enforced in two
places that mirror each other — Monitor.clean() and
MonitorWriteSerializer.validate() (see apps/monitors/models.py and
apps/monitors/serializers.py for why it's duplicated instead of the
serializer just calling full_clean()).

Neither can actually be triggered through the public API today: the
individual field ranges already guarantee it (max timeout_seconds is 30,
min interval_seconds is 60), so timeout_seconds can never legally reach or
exceed interval_seconds through a real request — see
tests/api/test_monitors.py's boundary test. These two are true unit tests:
they call the validation function directly with an attribute combination
the API could never actually produce, to prove the *rule itself* is
correct and would still catch a violation if the individual ranges ever
change.
"""

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.monitors.models import Monitor
from apps.monitors.serializers import MonitorWriteSerializer


def test_str_shows_name_and_url():
    monitor = Monitor(name="Prod API", url="https://example.com/health")

    assert str(monitor) == "Prod API (https://example.com/health)"


def test_model_clean_rejects_timeout_at_or_above_interval():
    monitor = Monitor(timeout_seconds=100, interval_seconds=60)

    with pytest.raises(DjangoValidationError):
        monitor.clean()


def test_model_clean_accepts_timeout_below_interval():
    monitor = Monitor(timeout_seconds=30, interval_seconds=60)

    monitor.clean()  # must not raise


def test_serializer_validate_rejects_timeout_at_or_above_interval():
    serializer = MonitorWriteSerializer()

    with pytest.raises(DRFValidationError):
        serializer.validate({"timeout_seconds": 100, "interval_seconds": 60})


def test_serializer_validate_accepts_timeout_below_interval():
    serializer = MonitorWriteSerializer()

    attrs = {"timeout_seconds": 30, "interval_seconds": 60}
    assert serializer.validate(attrs) == attrs


def test_model_rejects_a_body_on_a_get_monitor():
    monitor = Monitor(
        name="Prod API",
        url="https://example.com/health",
        method=Monitor.Method.GET,
        body='{"ping": true}',
        timeout_seconds=10,
        interval_seconds=300,
    )

    with pytest.raises(DjangoValidationError) as exc_info:
        monitor.clean()

    assert "body" in exc_info.value.error_dict


def test_model_allows_a_body_on_a_post_monitor():
    monitor = Monitor(
        name="Prod API",
        url="https://example.com/health",
        method=Monitor.Method.POST,
        body='{"ping": true}',
        timeout_seconds=10,
        interval_seconds=300,
    )

    monitor.clean()  # must not raise


def test_serializer_rejects_a_body_on_a_get_monitor():
    serializer = MonitorWriteSerializer()

    with pytest.raises(DRFValidationError) as exc_info:
        serializer.validate(
            {
                "method": Monitor.Method.GET,
                "body": '{"ping": true}',
                "timeout_seconds": 10,
                "interval_seconds": 300,
            }
        )

    assert "body" in exc_info.value.detail


def test_switching_a_post_monitor_to_get_without_clearing_the_body_is_rejected():
    # The PATCH shape that would otherwise slip through: only `method` is
    # in the request, so the body has to be read off the existing instance
    # to notice the combination is now illegal.
    instance = Monitor(
        name="Prod API",
        url="https://example.com/health",
        method=Monitor.Method.POST,
        body='{"ping": true}',
        timeout_seconds=10,
        interval_seconds=300,
    )
    serializer = MonitorWriteSerializer(instance=instance)

    with pytest.raises(DRFValidationError) as exc_info:
        serializer.validate({"method": Monitor.Method.GET})

    assert "body" in exc_info.value.detail
