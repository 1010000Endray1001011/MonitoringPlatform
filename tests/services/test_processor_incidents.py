from datetime import timedelta

import pytest
from django.utils import timezone

from apps.checks.models import CheckResult
from apps.checks.processor import process_check_result
from apps.incidents.models import Incident
from apps.monitors.models import Monitor
from integrations.http_probe import ProbeResult
from tests.factories import MonitorFactory

pytestmark = pytest.mark.django_db


def _failure(**overrides) -> ProbeResult:
    defaults = dict(
        success=False, error_type=CheckResult.ErrorType.TIMEOUT, error_message="timed out"
    )
    defaults.update(overrides)
    return ProbeResult(**defaults)


def _success(**overrides) -> ProbeResult:
    defaults = dict(success=True, status_code=200, response_time_ms=50)
    defaults.update(overrides)
    return ProbeResult(**defaults)


def test_crossing_the_failure_threshold_opens_exactly_one_incident():
    monitor = MonitorFactory(failure_threshold=2, success_threshold=1)
    now = timezone.now()

    process_check_result(monitor_id=monitor.id, checked_at=now, probe_result=_failure())
    assert Incident.objects.filter(monitor=monitor).count() == 0  # not yet — first failure only

    process_check_result(
        monitor_id=monitor.id, checked_at=now + timedelta(seconds=60), probe_result=_failure()
    )

    incidents = list(Incident.objects.filter(monitor=monitor))
    assert len(incidents) == 1
    incident = incidents[0]
    assert incident.status == Incident.Status.OPEN
    # started_at is the FIRST failing check in the streak, not the one
    # that happened to cross the threshold.
    assert incident.started_at == now
    assert incident.trigger_error_type == CheckResult.ErrorType.TIMEOUT
    assert incident.failed_checks_count == 2


def test_further_failures_while_already_down_do_not_open_a_second_incident():
    monitor = MonitorFactory(failure_threshold=2, success_threshold=1)
    now = timezone.now()

    for i in range(5):
        process_check_result(
            monitor_id=monitor.id,
            checked_at=now + timedelta(seconds=60 * i),
            probe_result=_failure(),
        )

    assert Incident.objects.filter(monitor=monitor).count() == 1


def test_recovery_resolves_the_open_incident_with_correct_duration():
    monitor = MonitorFactory(failure_threshold=1, success_threshold=1)
    now = timezone.now()

    process_check_result(monitor_id=monitor.id, checked_at=now, probe_result=_failure())
    recovered_at = now + timedelta(minutes=5)
    process_check_result(monitor_id=monitor.id, checked_at=recovered_at, probe_result=_success())

    incident = Incident.objects.get(monitor=monitor)
    assert incident.status == Incident.Status.RESOLVED
    assert incident.resolved_at == recovered_at
    assert incident.duration_seconds == 300
    assert incident.resolution_source == Incident.ResolutionSource.AUTO_RECOVERY


def test_a_second_outage_creates_a_brand_new_incident_not_a_reopened_one():
    monitor = MonitorFactory(failure_threshold=1, success_threshold=1)
    now = timezone.now()

    process_check_result(monitor_id=monitor.id, checked_at=now, probe_result=_failure())
    process_check_result(
        monitor_id=monitor.id, checked_at=now + timedelta(minutes=1), probe_result=_success()
    )
    process_check_result(
        monitor_id=monitor.id, checked_at=now + timedelta(minutes=2), probe_result=_failure()
    )

    incidents = list(Incident.objects.filter(monitor=monitor).order_by("started_at"))
    assert len(incidents) == 2
    assert incidents[0].status == Incident.Status.RESOLVED
    assert incidents[1].status == Incident.Status.OPEN


def test_a_stale_out_of_order_result_does_not_open_or_resolve_anything():
    monitor = MonitorFactory(
        failure_threshold=1, success_threshold=1, health_status=Monitor.HealthStatus.UP
    )
    now = timezone.now()

    # Establish last_checked_at at `now`.
    process_check_result(monitor_id=monitor.id, checked_at=now, probe_result=_success())

    # A late-arriving result timestamped *before* the one already
    # recorded — kept as history, but must not affect incidents.
    process_check_result(
        monitor_id=monitor.id,
        checked_at=now - timedelta(minutes=10),
        probe_result=_failure(),
    )

    assert Incident.objects.filter(monitor=monitor).count() == 0
    monitor.refresh_from_db()
    assert monitor.health_status == Monitor.HealthStatus.UP
