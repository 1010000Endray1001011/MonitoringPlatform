"""The only functions allowed to write to Incident. Nothing else in the
codebase should ever call `Incident.objects.create(...)` or set `.status`
directly — routing every write through here is what keeps the state
machine (OPEN -> ACKNOWLEDGED -> RESOLVED, RESOLVED is terminal) actually
enforced instead of just documented."""

from django.utils import timezone

from apps.common.exceptions import ConflictError

from .models import Incident
from .selectors import open_incident_for_monitor


def open_incident(
    *,
    monitor,
    started_at,
    trigger_error_type,
    trigger_status_code,
    failed_checks_count,
) -> Incident:
    # Checked explicitly rather than relying solely on the partial unique
    # index in the database: if that index ever did catch a real
    # duplicate, the resulting IntegrityError would roll back the entire
    # surrounding transaction — including the CheckResult row the caller
    # (processor.py) just wrote in the same block — silently losing a real
    # measurement, not just deduplicating an incident. select_for_update()
    # on the monitor already makes this race essentially impossible in
    # practice; this is a cheap extra guard against the failure mode being
    # worse than the check.
    existing = open_incident_for_monitor(monitor)
    if existing is not None:
        return existing

    return Incident.objects.create(
        monitor=monitor,
        status=Incident.Status.OPEN,
        started_at=started_at,
        trigger_error_type=trigger_error_type,
        trigger_status_code=trigger_status_code,
        failed_checks_count=failed_checks_count,
    )


def resolve_incident(*, incident: Incident, resolved_at, resolution_source: str) -> Incident:
    if incident.status == Incident.Status.RESOLVED:
        raise ConflictError("Incident is already resolved.")

    incident.status = Incident.Status.RESOLVED
    incident.resolved_at = resolved_at
    incident.duration_seconds = int((resolved_at - incident.started_at).total_seconds())
    incident.resolution_source = resolution_source
    incident.save(
        update_fields=[
            "status",
            "resolved_at",
            "duration_seconds",
            "resolution_source",
            "updated_at",
        ]
    )
    return incident


def acknowledge_incident(*, incident: Incident) -> Incident:
    if incident.status != Incident.Status.OPEN:
        raise ConflictError("Only an open incident can be acknowledged.")

    incident.status = Incident.Status.ACKNOWLEDGED
    incident.acknowledged_at = timezone.now()
    incident.save(update_fields=["status", "acknowledged_at", "updated_at"])
    return incident
