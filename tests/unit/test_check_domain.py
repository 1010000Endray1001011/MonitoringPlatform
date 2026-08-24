from datetime import datetime
from datetime import timezone as dt_timezone

from apps.checks.domain import TransitionResult, apply_check_outcome, compute_next_check_at
from apps.monitors.models import Monitor


def test_first_failure_does_not_bring_a_new_monitor_down():
    result = apply_check_outcome(
        current_status=Monitor.HealthStatus.NEW,
        consecutive_failures=0,
        consecutive_successes=0,
        failure_threshold=2,
        success_threshold=1,
        success=False,
    )

    assert result == TransitionResult(Monitor.HealthStatus.NEW, 1, 0)


def test_second_consecutive_failure_crosses_a_threshold_of_two():
    result = apply_check_outcome(
        current_status=Monitor.HealthStatus.NEW,
        consecutive_failures=1,
        consecutive_successes=0,
        failure_threshold=2,
        success_threshold=1,
        success=False,
    )

    assert result.health_status == Monitor.HealthStatus.DOWN
    assert result.consecutive_failures == 2


def test_single_success_recovers_a_down_monitor_with_threshold_one():
    result = apply_check_outcome(
        current_status=Monitor.HealthStatus.DOWN,
        consecutive_failures=3,
        consecutive_successes=0,
        failure_threshold=2,
        success_threshold=1,
        success=True,
    )

    assert result.health_status == Monitor.HealthStatus.UP
    assert result.consecutive_failures == 0
    assert result.consecutive_successes == 1


def test_success_streak_shorter_than_its_threshold_does_not_recover_yet():
    result = apply_check_outcome(
        current_status=Monitor.HealthStatus.DOWN,
        consecutive_failures=3,
        consecutive_successes=0,
        failure_threshold=2,
        success_threshold=2,
        success=True,
    )

    assert result.health_status == Monitor.HealthStatus.DOWN
    assert result.consecutive_successes == 1


def test_a_success_resets_the_failure_streak_even_without_recovering_yet():
    # threshold=3 for both directions, two failures already in, then one
    # success: the failure streak has to restart from zero even though a
    # single success isn't enough on its own to flip the status to UP.
    result = apply_check_outcome(
        current_status=Monitor.HealthStatus.NEW,
        consecutive_failures=2,
        consecutive_successes=0,
        failure_threshold=3,
        success_threshold=3,
        success=True,
    )

    assert result.consecutive_failures == 0
    assert result.consecutive_successes == 1
    assert result.health_status == Monitor.HealthStatus.NEW


def test_a_failure_resets_the_success_streak_even_without_going_down_yet():
    result = apply_check_outcome(
        current_status=Monitor.HealthStatus.UP,
        consecutive_failures=0,
        consecutive_successes=5,
        failure_threshold=2,
        success_threshold=2,
        success=False,
    )

    assert result.consecutive_successes == 0
    assert result.consecutive_failures == 1
    assert result.health_status == Monitor.HealthStatus.UP


def test_status_holds_steady_while_already_up_and_still_succeeding():
    result = apply_check_outcome(
        current_status=Monitor.HealthStatus.UP,
        consecutive_failures=0,
        consecutive_successes=10,
        failure_threshold=2,
        success_threshold=1,
        success=True,
    )

    assert result.health_status == Monitor.HealthStatus.UP
    assert result.consecutive_successes == 11


def test_compute_next_check_at_adds_the_interval_to_now():
    now = datetime(2026, 1, 1, tzinfo=dt_timezone.utc)

    result = compute_next_check_at(now=now, interval_seconds=300)

    assert result == datetime(2026, 1, 1, 0, 5, tzinfo=dt_timezone.utc)
