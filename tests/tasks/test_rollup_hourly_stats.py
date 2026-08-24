from datetime import timedelta

import pytest
from django.utils import timezone

from apps.checks.models import CheckResult, MonitorHourlyStat
from apps.checks.tasks import rollup_hourly_stats
from apps.incidents.models import Incident
from tests.factories import CheckResultFactory, MonitorFactory

pytestmark = pytest.mark.django_db


def _floored_hour(offset_hours: int):
    return timezone.now().replace(minute=0, second=0, microsecond=0) + timedelta(
        hours=offset_hours
    )


def test_aggregates_totals_and_response_times_for_the_hour():
    monitor = MonitorFactory()
    hour_start = _floored_hour(-2)
    CheckResultFactory(
        monitor=monitor,
        checked_at=hour_start + timedelta(minutes=5),
        success=True,
        response_time_ms=100,
    )
    CheckResultFactory(
        monitor=monitor,
        checked_at=hour_start + timedelta(minutes=10),
        success=True,
        response_time_ms=200,
    )
    CheckResultFactory(
        monitor=monitor,
        checked_at=hour_start + timedelta(minutes=15),
        success=False,
        status_code=None,
        response_time_ms=None,
        error_type=CheckResult.ErrorType.TIMEOUT,
    )

    rollup_hourly_stats(hour_start=hour_start)

    stat = MonitorHourlyStat.objects.get(monitor=monitor, hour_start=hour_start)
    assert stat.checks_total == 3
    assert stat.checks_failed == 1
    assert stat.avg_response_ms == 150
    assert stat.min_response_ms == 100
    assert stat.max_response_ms == 200


def test_downtime_seconds_reflects_an_overlapping_incident():
    monitor = MonitorFactory()
    hour_start = _floored_hour(-2)
    hour_end = hour_start + timedelta(hours=1)
    CheckResultFactory(monitor=monitor, checked_at=hour_start + timedelta(minutes=5), success=True)
    Incident.objects.create(
        monitor=monitor,
        status=Incident.Status.RESOLVED,
        started_at=hour_start + timedelta(minutes=20),
        resolved_at=hour_end,
        duration_seconds=2400,
        resolution_source=Incident.ResolutionSource.AUTO_RECOVERY,
    )

    rollup_hourly_stats(hour_start=hour_start)

    stat = MonitorHourlyStat.objects.get(monitor=monitor, hour_start=hour_start)
    assert stat.downtime_seconds == 40 * 60


def test_rerunning_for_the_same_hour_is_idempotent():
    monitor = MonitorFactory()
    hour_start = _floored_hour(-2)
    CheckResultFactory(monitor=monitor, checked_at=hour_start + timedelta(minutes=5), success=True)

    rollup_hourly_stats(hour_start=hour_start)
    rollup_hourly_stats(hour_start=hour_start)

    assert MonitorHourlyStat.objects.filter(monitor=monitor, hour_start=hour_start).count() == 1


def test_does_not_touch_the_current_not_yet_closed_hour():
    monitor = MonitorFactory()
    current_hour = _floored_hour(0)
    CheckResultFactory(
        monitor=monitor, checked_at=current_hour + timedelta(minutes=5), success=True
    )

    # Default hour_start (no argument) always resolves to the *previous*
    # hour, never the one still in progress.
    rollup_hourly_stats()

    assert not MonitorHourlyStat.objects.filter(monitor=monitor, hour_start=current_hour).exists()


def test_monitor_with_no_activity_in_the_hour_gets_no_row():
    MonitorFactory()  # exists, but has no CheckResult at all

    rollup_hourly_stats(hour_start=_floored_hour(-2))

    assert MonitorHourlyStat.objects.count() == 0
