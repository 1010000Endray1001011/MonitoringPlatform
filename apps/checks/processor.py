"""
Turns one probe outcome into a permanent record and, if it matters, a
change to the monitor's status. This is the one place that writes to
CheckResult and to a Monitor's engine-owned fields at the same time.
"""

from django.db import transaction

from apps.monitors.models import Monitor
from integrations.http_probe import ProbeResult

from . import domain
from .models import CheckResult


def process_check_result(*, monitor_id, checked_at, probe_result: ProbeResult) -> CheckResult:
    """Record `probe_result` and, unless it's stale, apply it to the
    monitor's streak counters and health status.

    Everything below happens in a single transaction, and nothing in it
    makes a network call — the probe already ran before this function was
    even called, so there's no slow I/O to hold a lock open for. The two
    things being protected are: the row this history entry becomes (which
    must never be lost or duplicated), and the monitor's own row, which
    gets `SELECT ... FOR UPDATE`'d so two results for the same monitor
    landing at nearly the same moment get serialised instead of racing.

    Raises `Monitor.DoesNotExist` if the monitor was deleted between being
    claimed and this call — the caller (the Celery task) is expected to
    treat that as "nothing to do", not as a failure worth retrying.
    """
    with transaction.atomic():
        monitor = Monitor.objects.select_for_update().get(id=monitor_id)

        check_result = CheckResult.objects.create(
            monitor=monitor,
            checked_at=checked_at,
            success=probe_result.success,
            status_code=probe_result.status_code,
            response_time_ms=probe_result.response_time_ms,
            error_type=probe_result.error_type,
            error_message=probe_result.error_message,
            response_size_bytes=probe_result.response_size_bytes,
        )

        # Two run_check executions for the same monitor can finish out of
        # order (the earlier attempt might have hit a slower target). The
        # result itself is always worth keeping as history — it's a real
        # measurement — but only the most recent attempt is allowed to move
        # the monitor's status. Without this guard, a late-arriving old
        # result could flip a monitor that's already recovered back to DOWN.
        if monitor.last_checked_at is not None and checked_at <= monitor.last_checked_at:
            return check_result

        transition = domain.apply_check_outcome(
            current_status=monitor.health_status,
            consecutive_failures=monitor.consecutive_failures,
            consecutive_successes=monitor.consecutive_successes,
            failure_threshold=monitor.failure_threshold,
            success_threshold=monitor.success_threshold,
            success=probe_result.success,
        )

        monitor.health_status = transition.health_status
        monitor.consecutive_failures = transition.consecutive_failures
        monitor.consecutive_successes = transition.consecutive_successes
        monitor.last_checked_at = checked_at
        monitor.save(
            update_fields=[
                "health_status",
                "consecutive_failures",
                "consecutive_successes",
                "last_checked_at",
                "updated_at",
            ]
        )

        # A status transition doesn't do anything beyond updating this row
        # yet — nothing here opens or closes an incident, and nothing sends
        # a notification. Both of those react to the same transition, once
        # there's somewhere for them to live.

    return check_result
