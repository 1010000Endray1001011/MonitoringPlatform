from datetime import timedelta

import pytest
from django.utils import timezone

from apps.checks.models import CheckResult
from apps.checks.processor import process_check_result
from apps.monitors.models import Monitor
from integrations.http_probe import ProbeResult
from tests.factories import MonitorFactory

pytestmark = pytest.mark.django_db


def _success_result(**overrides) -> ProbeResult:
    defaults = dict(success=True, status_code=200, response_time_ms=50)
    defaults.update(overrides)
    return ProbeResult(**defaults)


def _failure_result(**overrides) -> ProbeResult:
    defaults = dict(
        success=False, error_type=CheckResult.ErrorType.TIMEOUT, error_message="timed out"
    )
    defaults.update(overrides)
    return ProbeResult(**defaults)


def test_records_a_check_result_regardless_of_outcome():
    monitor = MonitorFactory()

    process_check_result(
        monitor_id=monitor.id, checked_at=timezone.now(), probe_result=_failure_result()
    )

    assert CheckResult.objects.filter(monitor=monitor, success=False).exists()


def test_a_single_failure_does_not_bring_a_monitor_down_at_threshold_two():
    monitor = MonitorFactory(
        failure_threshold=2, success_threshold=1, health_status=Monitor.HealthStatus.UP
    )

    process_check_result(
        monitor_id=monitor.id, checked_at=timezone.now(), probe_result=_failure_result()
    )

    monitor.refresh_from_db()
    assert monitor.health_status == Monitor.HealthStatus.UP
    assert monitor.consecutive_failures == 1


def test_reaching_the_failure_threshold_brings_the_monitor_down():
    monitor = MonitorFactory(
        failure_threshold=2, success_threshold=1, health_status=Monitor.HealthStatus.UP
    )
    now = timezone.now()

    process_check_result(monitor_id=monitor.id, checked_at=now, probe_result=_failure_result())
    process_check_result(
        monitor_id=monitor.id,
        checked_at=now + timedelta(seconds=1),
        probe_result=_failure_result(),
    )

    monitor.refresh_from_db()
    assert monitor.health_status == Monitor.HealthStatus.DOWN
    assert monitor.consecutive_failures == 2


def test_a_success_recovers_a_down_monitor_at_its_own_threshold():
    monitor = MonitorFactory(
        failure_threshold=2,
        success_threshold=1,
        health_status=Monitor.HealthStatus.DOWN,
        consecutive_failures=2,
    )

    process_check_result(
        monitor_id=monitor.id, checked_at=timezone.now(), probe_result=_success_result()
    )

    monitor.refresh_from_db()
    assert monitor.health_status == Monitor.HealthStatus.UP
    assert monitor.consecutive_failures == 0


def test_a_result_older_than_what_s_already_recorded_does_not_move_the_status():
    monitor = MonitorFactory(
        health_status=Monitor.HealthStatus.UP, success_threshold=1, failure_threshold=1
    )
    now = timezone.now()

    # The monitor goes down from a result timestamped "now"...
    process_check_result(monitor_id=monitor.id, checked_at=now, probe_result=_failure_result())
    monitor.refresh_from_db()
    assert monitor.health_status == Monitor.HealthStatus.DOWN

    # ...and then a *different* attempt, which had actually started earlier
    # but is only being processed now, comes back successful. It's real
    # history and gets saved either way...
    stale_checked_at = now - timedelta(seconds=30)
    stale_result = process_check_result(
        monitor_id=monitor.id, checked_at=stale_checked_at, probe_result=_success_result()
    )
    assert stale_result.success is True
    assert CheckResult.objects.filter(monitor=monitor).count() == 2

    # ...but it must not resurrect a monitor that's already correctly DOWN
    # according to the more recent measurement.
    monitor.refresh_from_db()
    assert monitor.health_status == Monitor.HealthStatus.DOWN


def test_raises_does_not_exist_for_a_monitor_deleted_before_processing():
    monitor = MonitorFactory()
    monitor_id = monitor.id
    monitor.delete()

    with pytest.raises(Monitor.DoesNotExist):
        process_check_result(
            monitor_id=monitor_id, checked_at=timezone.now(), probe_result=_success_result()
        )
