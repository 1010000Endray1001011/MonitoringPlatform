"""
Notifications half of the transition handling already covered for
incidents in test_processor_incidents.py: a DOWN/UP transition must
enqueue exactly the outbox rows a verified, active, attached channel is
entitled to — and nothing for a channel that isn't verified, isn't
active, or isn't attached to this monitor at all.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.checks.models import CheckResult
from apps.checks.processor import process_check_result
from apps.notifications.models import NotificationDelivery
from integrations.http_probe import ProbeResult
from tests.factories import MonitorFactory, NotificationChannelFactory

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


def test_a_down_transition_enqueues_a_notification_for_an_attached_verified_channel():
    monitor = MonitorFactory(failure_threshold=1, success_threshold=1)
    channel = NotificationChannelFactory(is_verified=True, is_active=True)
    channel.monitors.add(monitor)

    process_check_result(monitor_id=monitor.id, checked_at=timezone.now(), probe_result=_failure())

    deliveries = NotificationDelivery.objects.filter(channel=channel)
    assert deliveries.count() == 1
    assert deliveries.first().event_type == NotificationDelivery.EventType.INCIDENT_OPENED


def test_an_unattached_channel_gets_nothing():
    monitor = MonitorFactory(failure_threshold=1, success_threshold=1)
    NotificationChannelFactory(is_verified=True, is_active=True)  # not attached to `monitor`

    process_check_result(monitor_id=monitor.id, checked_at=timezone.now(), probe_result=_failure())

    assert NotificationDelivery.objects.count() == 0


def test_an_unverified_channel_gets_nothing():
    monitor = MonitorFactory(failure_threshold=1, success_threshold=1)
    channel = NotificationChannelFactory(is_verified=False, is_active=True)
    channel.monitors.add(monitor)

    process_check_result(monitor_id=monitor.id, checked_at=timezone.now(), probe_result=_failure())

    assert NotificationDelivery.objects.count() == 0


def test_an_inactive_channel_gets_nothing():
    monitor = MonitorFactory(failure_threshold=1, success_threshold=1)
    channel = NotificationChannelFactory(is_verified=True, is_active=False)
    channel.monitors.add(monitor)

    process_check_result(monitor_id=monitor.id, checked_at=timezone.now(), probe_result=_failure())

    assert NotificationDelivery.objects.count() == 0


def test_recovery_enqueues_a_resolved_notification_alongside_the_opened_one():
    monitor = MonitorFactory(failure_threshold=1, success_threshold=1)
    channel = NotificationChannelFactory(is_verified=True, is_active=True)
    channel.monitors.add(monitor)
    now = timezone.now()

    process_check_result(monitor_id=monitor.id, checked_at=now, probe_result=_failure())
    process_check_result(
        monitor_id=monitor.id, checked_at=now + timedelta(minutes=5), probe_result=_success()
    )

    event_types = set(
        NotificationDelivery.objects.filter(channel=channel).values_list("event_type", flat=True)
    )
    assert event_types == {
        NotificationDelivery.EventType.INCIDENT_OPENED,
        NotificationDelivery.EventType.INCIDENT_RESOLVED,
    }


def test_further_failures_while_already_down_do_not_enqueue_a_second_notification():
    monitor = MonitorFactory(failure_threshold=1, success_threshold=1)
    channel = NotificationChannelFactory(is_verified=True, is_active=True)
    channel.monitors.add(monitor)
    now = timezone.now()

    for i in range(4):
        process_check_result(
            monitor_id=monitor.id,
            checked_at=now + timedelta(seconds=60 * i),
            probe_result=_failure(),
        )

    assert (
        NotificationDelivery.objects.filter(
            channel=channel, event_type=NotificationDelivery.EventType.INCIDENT_OPENED
        ).count()
        == 1
    )
