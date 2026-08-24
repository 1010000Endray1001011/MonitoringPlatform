from django.db import models
from django.db.models import Q, UniqueConstraint

from apps.common.models import TimeStampedModel, UUIDPrimaryKeyModel
from integrations.http_probe.types import ALL_ERROR_TYPES


class Incident(UUIDPrimaryKeyModel, TimeStampedModel):
    """A period during which a monitor was down, as a first-class object.

    An Incident is created only at the moment a monitor's status actually
    crosses into DOWN (not on every failed check — see
    apps/checks/processor.py) and resolved only at the moment it crosses
    back to UP. `started_at`/`resolved_at` are the timestamps of the
    *first* check in each crossing streak, not the moment the threshold
    was reached — otherwise the recorded duration would systematically
    understate how long the outage actually lasted.

    `trigger_error_type`'s choices come from `integrations.http_probe.types`
    rather than from `apps.checks.models.CheckResult.ErrorType` on purpose:
    `integrations.http_probe` is a plain-Python package with no Django app
    dependencies, so both this app and `apps.checks` can source the same
    string constants from it independently. Importing `CheckResult`
    directly here would make `apps.incidents` depend on `apps.checks`,
    which is backwards — `apps.checks` is the one that depends on
    `apps.incidents` (it opens/resolves incidents from its own
    processing), never the other way around.
    """

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        ACKNOWLEDGED = "ACKNOWLEDGED", "Acknowledged"
        RESOLVED = "RESOLVED", "Resolved"

    class ResolutionSource(models.TextChoices):
        AUTO_RECOVERY = "AUTO_RECOVERY", "Auto recovery"
        # No MANUAL option: this MVP has no manual-close endpoint. An
        # incident only ever ends because the monitor actually recovered,
        # or because the reconciliation safety net below noticed a desync.
        SYSTEM_RECONCILE = "SYSTEM_RECONCILE", "System reconcile"

    monitor = models.ForeignKey(
        "monitors.Monitor", on_delete=models.CASCADE, related_name="incidents"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    started_at = models.DateTimeField()
    # Deliberately never cleared once set, even after the incident resolves
    # — "was this acknowledged at some point" stays a fact about the
    # incident's whole history, not just its currently-open phase.
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    # null=True on a CharField is usually wrong (two different "empty"
    # values, "" and NULL) — but both of these have `choices`, and "" isn't
    # a member of either. None unambiguously means "not applicable" (no
    # trigger yet, not resolved yet) instead of colliding with a real,
    # if empty, choice. Same reasoning as CheckResult.error_type.
    trigger_error_type = models.CharField(  # noqa: DJ001
        max_length=20,
        choices=[(value, value) for value in sorted(ALL_ERROR_TYPES)],
        null=True,
        blank=True,
    )
    trigger_status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    # Set once, at open time, to however many consecutive failures actually
    # triggered the incident. Deliberately not incremented further while
    # the incident stays open — it answers "how bad was the onset", not
    # "how many failed checks has this monitor logged since".
    failed_checks_count = models.PositiveIntegerField(default=0)
    resolution_source = models.CharField(  # noqa: DJ001
        max_length=20, choices=ResolutionSource.choices, null=True, blank=True
    )

    class Meta:
        indexes = [
            models.Index(fields=["monitor", "-started_at"], name="incident_monitor_started_idx"),
        ]
        constraints = [
            # The actual enforcement of "at most one open incident per
            # monitor" — the transition logic in processor.py is what's
            # supposed to guarantee this in the first place, but this is
            # what makes it true even if that logic ever has a bug.
            UniqueConstraint(
                fields=["monitor"],
                # Nested classes don't see names from the enclosing class
                # body, so this can't reference Status.RESOLVED directly —
                # the literal is exactly equivalent, since TextChoices
                # members are plain strings underneath.
                condition=~Q(status="RESOLVED"),
                name="incident_one_open_per_monitor",
            ),
        ]
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.monitor_id} {self.status} since {self.started_at}"


# A module-level alias, not just Incident.Status.choices used inline: the
# OpenAPI schema's ENUM_NAME_OVERRIDES (config/settings/base.py) needs a
# dotted path it can import, and drf-spectacular's loader can't reach
# through a nested class attribute like Incident.Status.choices directly.
INCIDENT_STATUS_CHOICES = Incident.Status.choices
