from datetime import timedelta

import pytest
from django.utils import timezone

from apps.common.exceptions import ConflictError, DomainError, QuotaExceededError
from apps.monitors import services
from apps.monitors.models import Monitor
from tests.factories import MonitorFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_create_monitor_schedules_first_check_immediately():
    user = UserFactory()
    before = timezone.now()

    monitor = services.create_monitor(user=user, name="API", url="http://example.com/")

    assert monitor.next_check_at >= before
    assert monitor.health_status == Monitor.HealthStatus.NEW


def test_create_monitor_enforces_quota():
    user = UserFactory(monitor_quota=1)
    services.create_monitor(user=user, name="First", url="http://example.com/")

    with pytest.raises(QuotaExceededError):
        services.create_monitor(user=user, name="Second", url="http://example2.com/")


def test_create_monitor_rejects_a_private_url(settings):
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False
    user = UserFactory()

    with pytest.raises(DomainError):
        services.create_monitor(user=user, name="Bad", url="http://127.0.0.1/")


def test_update_monitor_reschedules_when_interval_changes():
    stale_next_check = timezone.now() - timedelta(hours=1)
    monitor = MonitorFactory(interval_seconds=300, next_check_at=stale_next_check)

    updated = services.update_monitor(monitor=monitor, interval_seconds=600)

    assert updated.next_check_at > stale_next_check


def test_update_monitor_leaves_schedule_alone_when_interval_is_unchanged():
    fixed_time = timezone.now() - timedelta(hours=1)
    monitor = MonitorFactory(interval_seconds=300, next_check_at=fixed_time)

    updated = services.update_monitor(monitor=monitor, name="Renamed")

    assert updated.next_check_at == fixed_time


def test_update_monitor_revalidates_the_url(settings):
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False
    monitor = MonitorFactory()

    with pytest.raises(DomainError):
        services.update_monitor(monitor=monitor, url="http://127.0.0.1/")


def test_pause_monitor():
    monitor = MonitorFactory(is_enabled=True)

    paused = services.pause_monitor(monitor=monitor)

    assert paused.is_enabled is False


def test_pause_an_already_paused_monitor_raises_conflict():
    monitor = MonitorFactory(is_enabled=False)

    with pytest.raises(ConflictError):
        services.pause_monitor(monitor=monitor)


def test_resume_monitor_resets_streak_counters_but_keeps_health_status():
    monitor = MonitorFactory(
        is_enabled=False,
        consecutive_failures=3,
        consecutive_successes=0,
        health_status=Monitor.HealthStatus.DOWN,
    )

    resumed = services.resume_monitor(monitor=monitor)

    assert resumed.is_enabled is True
    assert resumed.consecutive_failures == 0
    # health_status is engine-owned and survives pause/resume —
    # only the user-owned is_enabled flag (and the now-stale streak) reset.
    assert resumed.health_status == Monitor.HealthStatus.DOWN


def test_resume_an_active_monitor_raises_conflict():
    monitor = MonitorFactory(is_enabled=True)

    with pytest.raises(ConflictError):
        services.resume_monitor(monitor=monitor)


def test_delete_monitor_removes_the_row():
    monitor = MonitorFactory()
    monitor_id = monitor.id

    services.delete_monitor(monitor=monitor)

    assert not Monitor.objects.filter(id=monitor_id).exists()
