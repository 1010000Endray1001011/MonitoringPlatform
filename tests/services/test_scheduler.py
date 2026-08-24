from datetime import timedelta

import pytest
from django.utils import timezone

from apps.checks.scheduler import claim_due_monitors
from tests.factories import MonitorFactory

pytestmark = pytest.mark.django_db


def test_claims_a_monitor_whose_next_check_at_is_in_the_past():
    monitor = MonitorFactory(next_check_at=timezone.now() - timedelta(seconds=1))

    claimed = claim_due_monitors()

    assert [m.id for m in claimed] == [monitor.id]


def test_does_not_claim_a_monitor_whose_next_check_at_is_in_the_future():
    MonitorFactory(next_check_at=timezone.now() + timedelta(hours=1))

    assert claim_due_monitors() == []


def test_does_not_claim_a_disabled_monitor_even_if_overdue():
    MonitorFactory(is_enabled=False, next_check_at=timezone.now() - timedelta(seconds=1))

    assert claim_due_monitors() == []


def test_pushes_next_check_at_forward_by_the_monitor_s_own_interval():
    monitor = MonitorFactory(
        interval_seconds=300, next_check_at=timezone.now() - timedelta(seconds=1)
    )
    before = timezone.now()

    claim_due_monitors()

    monitor.refresh_from_db()
    assert monitor.next_check_at >= before + timedelta(seconds=300)


def test_a_claimed_monitor_is_not_claimed_again_on_the_very_next_call():
    MonitorFactory(next_check_at=timezone.now() - timedelta(seconds=1))

    first_pass = claim_due_monitors()
    second_pass = claim_due_monitors()

    assert len(first_pass) == 1
    assert second_pass == []


def test_respects_the_batch_size():
    for _ in range(3):
        MonitorFactory(next_check_at=timezone.now() - timedelta(seconds=1))

    claimed = claim_due_monitors(batch_size=2)

    assert len(claimed) == 2


def test_orders_by_next_check_at_so_the_most_overdue_monitor_goes_first():
    less_overdue = MonitorFactory(next_check_at=timezone.now() - timedelta(seconds=10))
    more_overdue = MonitorFactory(next_check_at=timezone.now() - timedelta(seconds=100))

    claimed = claim_due_monitors()

    assert [m.id for m in claimed] == [more_overdue.id, less_overdue.id]
