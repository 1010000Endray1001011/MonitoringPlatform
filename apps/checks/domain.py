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

import math
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


@dataclass(frozen=True)
class ResponseTimeStats:
    avg: int | None
    minimum: int | None
    maximum: int | None
    p95: int | None


def compute_response_time_stats(response_times: list[int]) -> ResponseTimeStats:
    """Summarize one hour's worth of successful checks' response times.

    Plain Python rather than a database-side percentile aggregate: an
    hour holds at most a few dozen rows even at the shortest allowed
    interval, so there's nothing to gain from pushing this into SQL, and
    it makes the nearest-rank p95 below trivial to unit test with a
    hand-built list instead of needing real rows and a real database to
    match Postgres's own interpolation behaviour.
    """
    if not response_times:
        return ResponseTimeStats(avg=None, minimum=None, maximum=None, p95=None)

    ordered = sorted(response_times)
    # Nearest-rank percentile: the smallest value at or above which 95% of
    # the data falls. For n=1 this is just that one value; for n=100 it's
    # the 95th smallest (index 94, zero-based).
    rank = max(0, min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1))

    return ResponseTimeStats(
        avg=round(sum(ordered) / len(ordered)),
        minimum=ordered[0],
        maximum=ordered[-1],
        p95=ordered[rank],
    )


def compute_downtime_seconds(
    incident_windows: list[tuple[datetime, datetime | None]],
    *,
    hour_start: datetime,
    hour_end: datetime,
) -> int:
    """How many seconds of `[hour_start, hour_end)` were covered by an
    incident, given a list of `(started_at, resolved_at)` windows —
    `resolved_at=None` means still open, treated as covering through the
    end of the hour being measured.

    Each window is clipped to the hour before being summed, so an
    incident that started three days ago and is still open only
    contributes this one hour's worth of downtime to this one row, not
    its entire (so far unbounded) duration.
    """
    total = timedelta()
    for started_at, resolved_at in incident_windows:
        window_end = resolved_at or hour_end
        overlap_start = max(started_at, hour_start)
        overlap_end = min(window_end, hour_end)
        if overlap_end > overlap_start:
            total += overlap_end - overlap_start

    return int(total.total_seconds())
