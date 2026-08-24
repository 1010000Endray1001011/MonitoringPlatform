"""
Picks which monitors are due for a check right now, and makes sure two
concurrent callers can never pick the same one.
"""

from django.db import transaction
from django.utils import timezone

from apps.monitors.models import Monitor

from .domain import compute_next_check_at

# A ceiling on how many monitors one dispatch pass will claim. Without it, a
# worker that's been down for a while would come back to find every overdue
# monitor due at once and fire off all of them in a single burst — this
# caps that burst and lets the next tick pick up whatever's left instead.
DEFAULT_BATCH_SIZE = 100


def claim_due_monitors(*, batch_size: int = DEFAULT_BATCH_SIZE) -> list[Monitor]:
    """Atomically select up to `batch_size` due monitors and push their
    schedule forward, in one transaction.

    Two things happen together here, and it's the combination that
    prevents the same monitor from being claimed twice: `FOR UPDATE SKIP
    LOCKED` means a second, concurrent call to this function will never see
    a row the first call already has locked — it just skips past it and
    claims a different one instead of waiting or erroring. And advancing
    `next_check_at` before the transaction commits means a monitor that was
    just claimed won't look "due" again on the very next tick, even though
    the check itself hasn't actually run yet.

    Deliberately not `select_for_update().iterator()` or similar streaming
    approach — the whole batch is small (capped by `batch_size`) and needs
    to be materialised anyway to compute each row's new `next_check_at`, so
    there's nothing to gain from avoiding the list().
    """
    with transaction.atomic():
        due = list(
            Monitor.objects.select_for_update(skip_locked=True)
            .filter(is_enabled=True, next_check_at__lte=timezone.now())
            .order_by("next_check_at")[:batch_size]
        )
        if not due:
            return []

        now = timezone.now()
        for monitor in due:
            monitor.next_check_at = compute_next_check_at(
                now=now, interval_seconds=monitor.interval_seconds
            )
        Monitor.objects.bulk_update(due, ["next_check_at"])

    return due
