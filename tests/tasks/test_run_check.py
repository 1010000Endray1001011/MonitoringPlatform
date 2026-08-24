"""
`run_check` tested by calling it directly / via `.apply()` — no broker
needed, since `apps.checks.tasks.get_http_probe` is monkeypatched to return
a fake instead of making real HTTP calls. `CELERY_TASK_ALWAYS_EAGER` means
`.apply()`'s retry handling runs synchronously too, so a retried task's
second attempt is visible within the same test.
"""

import pytest
from celery.exceptions import Retry
from django.core.cache import cache

from apps.checks import tasks
from apps.checks.models import CheckResult
from apps.monitors.models import Monitor
from integrations.http_probe import FakeHttpProbe, ProbeResult
from tests.factories import MonitorFactory

pytestmark = pytest.mark.django_db


def test_records_a_successful_probe_and_updates_health_status(monkeypatch):
    monitor = MonitorFactory(health_status=Monitor.HealthStatus.NEW, success_threshold=1)
    fake = FakeHttpProbe(ProbeResult(success=True, status_code=200, response_time_ms=42))
    monkeypatch.setattr(tasks, "get_http_probe", lambda: fake)

    tasks.run_check(monitor.id)

    monitor.refresh_from_db()
    assert monitor.health_status == Monitor.HealthStatus.UP
    assert CheckResult.objects.filter(monitor=monitor, success=True).exists()
    assert len(fake.calls) == 1


def test_a_monitor_that_no_longer_exists_is_handled_silently(monkeypatch):
    fake = FakeHttpProbe()
    monkeypatch.setattr(tasks, "get_http_probe", lambda: fake)

    tasks.run_check("00000000-0000-0000-0000-000000000000")

    assert fake.calls == []


def test_a_paused_monitor_is_never_probed(monkeypatch):
    monitor = MonitorFactory(is_enabled=False)
    fake = FakeHttpProbe()
    monkeypatch.setattr(tasks, "get_http_probe", lambda: fake)

    tasks.run_check(monitor.id)

    assert fake.calls == []


def test_a_held_lock_prevents_a_second_probe_of_the_same_monitor(monkeypatch):
    monitor = MonitorFactory()
    fake = FakeHttpProbe()
    monkeypatch.setattr(tasks, "get_http_probe", lambda: fake)
    lock_key = f"check:lock:{monitor.id}"
    cache.add(lock_key, "1", timeout=60)

    tasks.run_check(monitor.id)

    assert fake.calls == []
    cache.delete(lock_key)


def test_the_lock_is_released_once_the_check_finishes(monkeypatch):
    monitor = MonitorFactory()
    fake = FakeHttpProbe()
    monkeypatch.setattr(tasks, "get_http_probe", lambda: fake)

    tasks.run_check(monitor.id)

    assert cache.get(f"check:lock:{monitor.id}") is None


def test_a_monitor_deleted_mid_check_is_handled_silently(monkeypatch):
    # The narrow race this guards against: the monitor still existed when
    # run_check fetched it, but is gone by the time process_check_result
    # tries to write the result against it — the measurement was made, but
    # there's nowhere left to record it. That's not a failure worth
    # surfacing, let alone retrying.
    monitor = MonitorFactory()
    fake = FakeHttpProbe()
    monkeypatch.setattr(tasks, "get_http_probe", lambda: fake)

    def _raise_does_not_exist(**kwargs):
        raise Monitor.DoesNotExist

    monkeypatch.setattr(tasks.processor, "process_check_result", _raise_does_not_exist)

    tasks.run_check(monitor.id)  # must not raise

    assert cache.get(f"check:lock:{monitor.id}") is None


def test_does_not_retry_on_an_error_that_s_a_fact_about_the_target(monkeypatch):
    monitor = MonitorFactory()
    fake = FakeHttpProbe(
        ProbeResult(success=False, error_type=CheckResult.ErrorType.TIMEOUT, error_message="slow")
    )
    monkeypatch.setattr(tasks, "get_http_probe", lambda: fake)

    tasks.run_check.apply(args=[monitor.id])

    assert len(fake.calls) == 1
    assert CheckResult.objects.filter(monitor=monitor, error_type="TIMEOUT").count() == 1


def test_an_internal_error_asks_celery_to_retry(monkeypatch):
    monitor = MonitorFactory()
    fake = FakeHttpProbe(
        ProbeResult(
            success=False, error_type=CheckResult.ErrorType.INTERNAL_ERROR, error_message="glitch"
        )
    )
    monkeypatch.setattr(tasks, "get_http_probe", lambda: fake)

    # `self.retry()` always raises `Retry` — under CELERY_TASK_ALWAYS_EAGER
    # it isn't the worker but the caller who's left to see this, since
    # there's no broker to hand the retry off to; a real worker sees the
    # same exception and re-queues the task instead of letting it surface.
    with pytest.raises(Retry):
        tasks.run_check.apply(args=[monitor.id])

    # The measurement that triggered the retry is still real and already
    # committed by the time the retry is requested — it isn't discarded
    # just because the task itself hasn't finished successfully yet.
    assert CheckResult.objects.filter(monitor=monitor, error_type="INTERNAL_ERROR").exists()
    # And the lock has to be released, not left held until it times out,
    # or the actual retry (a fresh task run later) would find it locked.
    assert cache.get(f"check:lock:{monitor.id}") is None
