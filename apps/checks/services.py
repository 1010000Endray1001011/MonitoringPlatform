"""Orchestration for things a user triggers directly, as opposed to what
the scheduler triggers on its own cadence."""

from django.db import transaction

from apps.common.exceptions import ConflictError
from apps.monitors.models import Monitor

from .tasks import run_check


def request_immediate_check(*, monitor: Monitor) -> None:
    if not monitor.is_enabled:
        raise ConflictError("Cannot check a paused monitor.")

    # Deferred until the surrounding request's transaction actually commits
    # — otherwise a task could start probing before the caller's own
    # changes (or even the fact that this endpoint was ever called
    # successfully) have landed in the database.
    transaction.on_commit(lambda: run_check.delay(monitor.id))
