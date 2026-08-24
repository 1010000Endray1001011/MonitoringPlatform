"""
Pure decision logic for the monitoring engine — no ORM, no I/O, no imports
of anything that talks to a database or the network. Everything here is a
plain function over plain values, which is what makes the trickiest part of
this whole system (deciding whether one more failed check means a monitor
is actually down) testable in milliseconds without a database.

apps.checks.processor is the only caller: it does the actual reading and
writing, and treats these functions as the source of truth for what the new
numbers should be.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from apps.monitors.models import Monitor


@dataclass(frozen=True)
class TransitionResult:
    health_status: str
    consecutive_failures: int
    consecutive_successes: int


def apply_check_outcome(
    *,
    current_status: str,
    consecutive_failures: int,
    consecutive_successes: int,
    failure_threshold: int,
    success_threshold: int,
    success: bool,
) -> TransitionResult:
    """Fold one check's outcome into the running streak, and decide whether
    that streak is now long enough to flip the monitor's health status.

    A single failed check never means DOWN, and a single successful check
    never means UP on its own — a run of `failure_threshold` (or
    `success_threshold`) consecutive results in the same direction is what
    it takes. That threshold is what tells a genuine outage apart from one
    off network blip: every attempt still gets recorded either way, but the
    status only moves once the same outcome has repeated enough times in a
    row to be believable. One immediate side effect: a check that goes the
    other way resets the *opposite* streak back to zero — a single success
    in the middle of a losing streak means the losing streak has to start
    over, not just pause.
    """
    if success:
        consecutive_failures = 0
        consecutive_successes += 1
    else:
        consecutive_successes = 0
        consecutive_failures += 1

    if success and consecutive_successes >= success_threshold:
        new_status = Monitor.HealthStatus.UP
    elif not success and consecutive_failures >= failure_threshold:
        new_status = Monitor.HealthStatus.DOWN
    else:
        # Streak isn't long enough yet to justify a change — the monitor
        # keeps whatever status it already had.
        new_status = current_status

    return TransitionResult(
        health_status=new_status,
        consecutive_failures=consecutive_failures,
        consecutive_successes=consecutive_successes,
    )


def compute_next_check_at(*, now: datetime, interval_seconds: int) -> datetime:
    # Deliberately `now + interval`, never `previous_next_check_at +
    # interval`. If the system falls behind (a stalled worker, a deploy),
    # this doesn't try to "catch up" by cramming in the missed checks —
    # there's nothing useful to measure about the past, so the schedule
    # just picks up again from wherever the present actually is.
    return now + timedelta(seconds=interval_seconds)
