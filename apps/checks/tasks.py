"""
The two Celery tasks that make checks actually happen. Both are
deliberately thin — the real logic lives in scheduler.py, processor.py and
integrations.http_probe, all of which can be (and are) tested without
Celery or a broker at all. These tasks just wire that logic into the
background-task machinery: pull work off a schedule, hand it to a worker,
and translate the result into a retry decision.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.incidents import selectors as incidents_selectors
from apps.monitors.models import Monitor
from integrations.http_probe import ProbeRequest, get_http_probe

from . import domain, processor, scheduler
from .models import CheckResult, MonitorHourlyStat

logger = logging.getLogger(__name__)


@shared_task(name="apps.checks.tasks.dispatch_due_checks")
def dispatch_due_checks() -> None:
    # One transaction wraps both the claim and the enqueueing, so
    # `on_commit` genuinely defers until the claim (the next_check_at push)
    # has landed — not until whatever the *next* unrelated commit happens
    # to be, which is what it would defer to if this were called outside
    # any transaction at all.
    with transaction.atomic():
        due_monitors = scheduler.claim_due_monitors()
        if due_monitors:
            # Below INFO would hide this from production's default level;
            # skipped on an empty tick (every 30s, most of them empty on a
            # small install) so the log isn't dominated by "did nothing".
            logger.info("dispatching due checks", extra={"monitor_count": len(due_monitors)})
        for monitor in due_monitors:
            # `monitor_id=monitor.id` is a default argument, not a closure
            # over the loop variable — without it every lambda in this loop
            # would end up looking up whatever `monitor` is bound to by the
            # time it actually runs, which is the last one in the list.
            transaction.on_commit(lambda monitor_id=monitor.id: run_check.delay(monitor_id))


@shared_task(
    name="apps.checks.tasks.run_check",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
    # Explicit even though it's Celery's own default: a redelivered
    # duplicate of this task must never repeat an HTTP request against
    # someone else's server, so losing a check entirely (if the worker
    # dies mid-probe) is the safer failure mode than risking a double
    # request. acks_late=True would trade that risk the other way.
    acks_late=False,
)
def run_check(self, monitor_id) -> None:
    try:
        monitor = Monitor.objects.get(id=monitor_id, is_enabled=True)
    except Monitor.DoesNotExist:
        # Deleted, or paused, since being claimed — there's nothing to
        # check and nothing to report; this is not an error condition.
        return

    lock_key = f"check:lock:{monitor_id}"
    # Held for roughly the lifetime of one probe attempt. This exists
    # alongside the scheduler's own claim-then-reschedule guarantee because
    # it protects against a different failure mode: the broker redelivering
    # this exact task (Redis is an at-least-once broker) rather than the
    # scheduler claiming the same monitor twice.
    if not cache.add(lock_key, "1", timeout=monitor.timeout_seconds + 10):
        return

    try:
        checked_at = timezone.now()
        result = get_http_probe().probe(
            ProbeRequest(
                url=monitor.url,
                method=monitor.method,
                timeout_seconds=monitor.timeout_seconds,
                expected_status=monitor.expected_status,
                headers=monitor.headers,
                body=monitor.body,
            )
        )

        try:
            processor.process_check_result(
                monitor_id=monitor.id, checked_at=checked_at, probe_result=result
            )
        except Monitor.DoesNotExist:
            # The monitor was deleted in the gap between the fetch above
            # and the write inside process_check_result — the measurement
            # was made but there's nowhere left to record it against.
            return

        logger.info(
            "check completed",
            extra={
                "monitor_id": str(monitor.id),
                "success": result.success,
                "status_code": result.status_code,
                "error_type": result.error_type,
            },
        )

        if result.error_type == CheckResult.ErrorType.INTERNAL_ERROR:
            # The only outcome that's our own fault rather than a fact
            # about the target — everything else (a timeout, a refused
            # connection, an unexpected status) has already been recorded
            # as-is and must not be repeated.
            logger.warning(
                "check failed on our end, retrying",
                extra={"monitor_id": str(monitor.id), "error_message": result.error_message},
            )
            raise self.retry(
                exc=RuntimeError(result.error_message or "probe failed for an unknown reason")
            )
    finally:
        cache.delete(lock_key)


@shared_task(name="apps.checks.tasks.rollup_hourly_stats")
def rollup_hourly_stats(hour_start=None) -> None:
    """Summarize one hour's CheckResult rows into one MonitorHourlyStat row
    per monitor that had any activity that hour.

    `hour_start` is normally left unset — it defaults to the most recently
    *fully closed* hour, never the current one, since that's still being
    written to. The parameter exists for manual backfill and for tests
    that need a specific, known hour rather than whatever "now" happens to
    be. `update_or_create` on the (monitor, hour_start) unique constraint
    makes a re-run for an hour that's already aggregated idempotent —
    it recomputes and overwrites, it doesn't duplicate.
    """
    if hour_start is None:
        hour_start = timezone.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    hour_end = hour_start + timedelta(hours=1)

    monitors_with_activity = Monitor.objects.filter(
        id__in=CheckResult.objects.filter(
            checked_at__gte=hour_start, checked_at__lt=hour_end
        ).values("monitor_id")
    )

    for monitor in monitors_with_activity:
        checks_in_hour = CheckResult.objects.filter(
            monitor=monitor, checked_at__gte=hour_start, checked_at__lt=hour_end
        )
        totals = checks_in_hour.aggregate(
            total=Count("id"), failed=Count("id", filter=Q(success=False))
        )
        response_times = list(
            checks_in_hour.filter(success=True).values_list("response_time_ms", flat=True)
        )
        response_stats = domain.compute_response_time_stats(response_times)

        incident_windows = incidents_selectors.incident_windows_for_monitor(
            monitor, start=hour_start, end=hour_end
        )
        downtime_seconds = domain.compute_downtime_seconds(
            incident_windows, hour_start=hour_start, hour_end=hour_end
        )

        MonitorHourlyStat.objects.update_or_create(
            monitor=monitor,
            hour_start=hour_start,
            defaults={
                "checks_total": totals["total"],
                "checks_failed": totals["failed"],
                "avg_response_ms": response_stats.avg,
                "min_response_ms": response_stats.minimum,
                "max_response_ms": response_stats.maximum,
                "p95_response_ms": response_stats.p95,
                "downtime_seconds": downtime_seconds,
            },
        )


@shared_task(name="apps.checks.tasks.purge_old_check_results")
def purge_old_check_results() -> None:
    """Delete raw CheckResult rows once they're old enough *and* already
    aggregated into an hourly stat — never the other way around, since
    deleting first would lose data the rollup hasn't summarized yet.

    Bounded to a rolling window (`window_start` to `cutoff`) rather than
    "every aggregated hour older than cutoff": aggregates themselves are
    never deleted, so an unbounded query would re-scan the *entire*
    history of old, already-empty hours again every single day, forever.
    The window only needs to be a few days wide — anything this task
    hasn't caught within that margin will simply be caught the next time
    it runs.
    """
    cutoff = timezone.now() - timedelta(days=settings.MONITORING_RAW_RETENTION_DAYS)
    window_start = cutoff - timedelta(days=3)

    stats_to_purge = MonitorHourlyStat.objects.filter(
        hour_start__gte=window_start, hour_start__lt=cutoff
    )
    for stat in stats_to_purge:
        hour_end = stat.hour_start + timedelta(hours=1)
        CheckResult.objects.filter(
            monitor_id=stat.monitor_id, checked_at__gte=stat.hour_start, checked_at__lt=hour_end
        ).delete()
