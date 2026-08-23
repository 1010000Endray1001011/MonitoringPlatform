"""
Application/service layer for Monitor

- Views only translate HTTP <-> serializer data and call a service function.
- These functions hold the actual business rules (quota, rescheduling,
  state transitions) and own the transaction/`full_clean()` call.
- `apps/monitors/models.py` and `apps/common/validators.py` hold the
  invariants that don't depend on *who* is calling (field ranges, the SSRF
  policy) — the service doesn't repeat those, it just makes sure they run.

Every function here takes an already-resolved `Monitor` (or `user`) rather
than an id — looking a monitor up by id and checking ownership is the view's
job, via `apps.monitors.selectors.monitors_for_user` + DRF's `get_object_or_404`.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone

from apps.common.exceptions import ConflictError, DomainError, QuotaExceededError

from .models import Monitor
from .selectors import monitors_for_user


def _full_clean_or_raise(monitor: Monitor) -> None:
    """Run Django's model-level validation and translate its exception type.

    `full_clean()` raises `django.core.exceptions.ValidationError`, which our
    DRF exception handler (apps/common/exceptions.py) doesn't know about —
    it only understands DRF's own ValidationError and our `DomainError`
    family. In normal API use this should never actually fire, because the
    serializer already validated the same rules before the service was
    called; it's a backstop for callers that bypass the serializer (a future
    management command, a data migration).
    """
    try:
        monitor.full_clean()
    except DjangoValidationError as exc:
        details = exc.message_dict if hasattr(exc, "message_dict") else {"__all__": exc.messages}
        raise DomainError("Invalid monitor configuration.", details=details) from exc


def create_monitor(*, user, **fields) -> Monitor:
    # Quota is checked here, not as a DB constraint: it's a per-user business
    # rule ("how many monitors can this account have"), not a fact about the
    # Monitor row itself, so it doesn't belong in Monitor's own invariants.
    if monitors_for_user(user).count() >= user.monitor_quota:
        raise QuotaExceededError(
            f"Monitor quota exceeded: this account is limited to {user.monitor_quota} monitors."
        )

    # A brand-new monitor is due for its first check immediately — the next
    # dispatcher tick (every 30s, Chunk 3) will pick it up.
    monitor = Monitor(user=user, next_check_at=timezone.now(), **fields)
    _full_clean_or_raise(monitor)
    monitor.save()
    return monitor


def update_monitor(*, monitor: Monitor, **fields) -> Monitor:
    interval_changed = (
        "interval_seconds" in fields and fields["interval_seconds"] != monitor.interval_seconds
    )

    for field_name, value in fields.items():
        setattr(monitor, field_name, value)

    if interval_changed:
        # The old cadence is no longer meaningful once it's changed — rather
        # than wait out whatever was left of the previous interval, make the
        # monitor due again right away so it starts on the new schedule.
        monitor.next_check_at = timezone.now()

    _full_clean_or_raise(monitor)
    monitor.save()
    return monitor


def pause_monitor(*, monitor: Monitor) -> Monitor:
    if not monitor.is_enabled:
        raise ConflictError("Monitor is already paused.")

    monitor.is_enabled = False
    monitor.save(update_fields=["is_enabled", "updated_at"])
    return monitor


def resume_monitor(*, monitor: Monitor) -> Monitor:
    if monitor.is_enabled:
        raise ConflictError("Monitor is already active.")

    # `health_status` is deliberately left untouched the monitor remembers whatever it was before the pause. The
    # streak counters do reset, though — a stale streak from before the
    # pause shouldn't count towards a state transition after it.
    monitor.is_enabled = True
    monitor.consecutive_failures = 0
    monitor.consecutive_successes = 0
    monitor.next_check_at = timezone.now()
    monitor.save(
        update_fields=[
            "is_enabled",
            "consecutive_failures",
            "consecutive_successes",
            "next_check_at",
            "updated_at",
        ]
    )
    return monitor


def delete_monitor(*, monitor: Monitor) -> None:
    monitor.delete()
