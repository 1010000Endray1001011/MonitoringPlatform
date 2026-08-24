from datetime import timedelta

import pytest
from django.utils import timezone

from apps.checks.models import CheckResult
from apps.checks.tasks import purge_old_check_results
from tests.factories import CheckResultFactory, MonitorFactory, MonitorHourlyStatFactory

pytestmark = pytest.mark.django_db


def _floored_hour(days_ago: int):
    return (timezone.now() - timedelta(days=days_ago)).replace(minute=0, second=0, microsecond=0)


def test_deletes_raw_rows_whose_hour_already_has_an_aggregate():
    monitor = MonitorFactory()
    # Comfortably inside the rolling window this task scans (retention=7d
    # by default, window extends 3 days further back — 8 days ago lands
    # inside [cutoff-3d, cutoff) without sitting right on either edge).
    hour_start = _floored_hour(8)
    CheckResultFactory(monitor=monitor, checked_at=hour_start + timedelta(minutes=5))
    MonitorHourlyStatFactory(monitor=monitor, hour_start=hour_start)

    purge_old_check_results()

    assert not CheckResult.objects.filter(monitor=monitor).exists()


def test_leaves_old_rows_alone_when_their_hour_has_no_aggregate_yet():
    monitor = MonitorFactory()
    hour_start = _floored_hour(8)
    CheckResultFactory(monitor=monitor, checked_at=hour_start + timedelta(minutes=5))
    # Deliberately no MonitorHourlyStat for this hour.

    purge_old_check_results()

    assert CheckResult.objects.filter(monitor=monitor).exists()


def test_leaves_recent_aggregated_rows_alone():
    monitor = MonitorFactory()
    hour_start = _floored_hour(1)  # well inside the retention window
    CheckResultFactory(monitor=monitor, checked_at=hour_start + timedelta(minutes=5))
    MonitorHourlyStatFactory(monitor=monitor, hour_start=hour_start)

    purge_old_check_results()

    assert CheckResult.objects.filter(monitor=monitor).exists()


def test_leaves_rows_outside_the_rolling_window_alone():
    monitor = MonitorFactory()
    # Far older than the window this task scans — a row this old that
    # somehow still exists is not this run's problem to clean up.
    hour_start = _floored_hour(30)
    CheckResultFactory(monitor=monitor, checked_at=hour_start + timedelta(minutes=5))
    MonitorHourlyStatFactory(monitor=monitor, hour_start=hour_start)

    purge_old_check_results()

    assert CheckResult.objects.filter(monitor=monitor).exists()
