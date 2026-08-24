"""
The two Celery tasks that make checks actually happen. Both are
deliberately thin — the real logic lives in scheduler.py, processor.py and
integrations.http_probe, all of which can be (and are) tested without
Celery or a broker at all. These tasks just wire that logic into the
background-task machinery: pull work off a schedule, hand it to a worker,
and translate the result into a retry decision.
"""

import logging

from celery import shared_task
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.monitors.models import Monitor
from integrations.http_probe import ProbeRequest, get_http_probe

from . import processor, scheduler
from .models import CheckResult

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

        if result.error_type == CheckResult.ErrorType.INTERNAL_ERROR:
            # The only outcome that's our own fault rather than a fact
            # about the target — everything else (a timeout, a refused
            # connection, an unexpected status) has already been recorded
            # as-is and must not be repeated.
            raise self.retry(
                exc=RuntimeError(result.error_message or "probe failed for an unknown reason")
            )
    finally:
        cache.delete(lock_key)
