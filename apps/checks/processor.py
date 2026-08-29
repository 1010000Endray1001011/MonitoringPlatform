"""
Turns one probe outcome into a permanent record and, if it matters, a
change to the monitor's status — and, if that change is a real transition,
opens or resolves the Incident that represents it and enqueues whatever
notifications that incident event needs to go out. This is the one place
that writes to CheckResult and to a Monitor's engine-owned fields at the
same time, and the one place that decides an Incident needs to exist at
all (apps.incidents.services only ever writes an Incident when told to).
"""

from django.db import transaction

from apps.incidents import selectors as incidents_selectors
from apps.incidents import services as incidents_services
from apps.incidents.models import Incident
from apps.monitors.models import Monitor
from apps.notifications import services as notifications_services
from apps.notifications.models import NotificationDelivery
from integrations.http_probe import ProbeResult

from . import domain
from .models import CheckResult
from .selectors import streak_start_at


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
    That same lock is what makes the Incident handling below safe too —
    two results for one monitor can never both decide a transition
    happened at the same time.

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

        old_status = monitor.health_status
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

        # An incident is only ever opened or resolved on the boundary
        # crossing itself, never on every failed/successful check — that's
        # exactly what apply_check_outcome's thresholds already decided
        # above by changing (or not changing) health_status. Enqueueing a
        # notification happens in the same transaction as the incident
        # change it's about, via the outbox (apps.notifications.services)
        # — actually sending it is someone else's job, later, off this
        # transaction entirely.
        if transition.health_status != old_status:
            if transition.health_status == Monitor.HealthStatus.DOWN:
                # This check is itself the most recent of the failing
                # streak — it was already written above, so it's visible
                # to this query within the same transaction.
                started_at = (
                    streak_start_at(monitor, success=False, count=transition.consecutive_failures)
                    or checked_at
                )
                incident = incidents_services.open_incident(
                    monitor=monitor,
                    started_at=started_at,
                    trigger_error_type=probe_result.error_type,
                    trigger_status_code=probe_result.status_code,
                    failed_checks_count=transition.consecutive_failures,
                )
                notifications_services.enqueue_incident_notifications(
                    incident=incident, event_type=NotificationDelivery.EventType.INCIDENT_OPENED
                )
            elif transition.health_status == Monitor.HealthStatus.UP:
                open_incident = incidents_selectors.open_incident_for_monitor(monitor)
                if open_incident is not None:
                    resolved_at = (
                        streak_start_at(
                            monitor, success=True, count=transition.consecutive_successes
                        )
                        or checked_at
                    )
                    incident = incidents_services.resolve_incident(
                        incident=open_incident,
                        resolved_at=resolved_at,
                        resolution_source=Incident.ResolutionSource.AUTO_RECOVERY,
                    )
                    notifications_services.enqueue_incident_notifications(
                        incident=incident,
                        event_type=NotificationDelivery.EventType.INCIDENT_RESOLVED,
                    )

    return check_result
