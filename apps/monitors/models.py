from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import CheckConstraint, F, Q

from apps.common.models import TimeStampedModel, UUIDPrimaryKeyModel
from apps.common.validators import validate_monitor_url

# Discrete set of intervals a monitor can run at, rather than an arbitrary
# integer. This caps load per user/instance and keeps the dispatcher's
# "who's due" query cheap. Baked into a DB CheckConstraint below, so it's
# also a plain module constant (not a Django setting) — a CHECK constraint
# is fixed into the schema at migration time and can't read settings.py at
# runtime, so there'd be nothing to gain from making it "configurable".
ALLOWED_INTERVALS = (60, 120, 300, 600, 900, 1800, 3600)


class Monitor(UUIDPrimaryKeyModel, TimeStampedModel):
    """A single HTTP endpoint the user wants checked periodically.

    - The first group is configuration the user sets through the API.


    Splitting `is_enabled` (user-owned: "should this run at all?") from
    `health_status` (engine-owned: "is it currently up?") instead of one
    combined NEW/UP/DOWN/PAUSED enum is what avoids a write race between a
    user hitting pause and the engine concurrently recording a result
    """

    class Method(models.TextChoices):
        GET = "GET", "GET"
        HEAD = "HEAD", "HEAD"
        POST = "POST", "POST"

    class HealthStatus(models.TextChoices):
        NEW = "NEW", "New"
        UP = "UP", "Up"
        DOWN = "DOWN", "Down"

    # --- owned by the user: set on create, changeable via PATCH ------------
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="monitors"
    )
    name = models.CharField(max_length=100)
    # validate_monitor_url runs on every save via full_clean(), and DRF's
    # ModelSerializer picks it up automatically for API validation too —
    # see apps/common/validators.py for why one function covers both.
    url = models.URLField(max_length=2048, validators=[validate_monitor_url])
    method = models.CharField(max_length=4, choices=Method.choices, default=Method.GET)
    expected_status = models.PositiveSmallIntegerField(
        default=200, validators=[MinValueValidator(100), MaxValueValidator(599)]
    )
    # `choices` (not just a plain IntegerField) so full_clean()/DRF/admin all
    # reject an interval outside ALLOWED_INTERVALS with a normal validation
    # error — the matching CheckConstraint in Meta is the DB-level backstop
    # for the rare write path that skips model validation entirely.
    interval_seconds = models.PositiveIntegerField(
        default=300, choices=[(value, str(value)) for value in ALLOWED_INTERVALS]
    )
    timeout_seconds = models.PositiveSmallIntegerField(
        default=10, validators=[MinValueValidator(1), MaxValueValidator(30)]
    )
    headers = models.JSONField(default=dict, blank=True)
    failure_threshold = models.PositiveSmallIntegerField(
        default=2, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    success_threshold = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    is_enabled = models.BooleanField(default=True)

    # --- owned by the monitoring engine: read-only through the API ---------
    health_status = models.CharField(
        max_length=4, choices=HealthStatus.choices, default=HealthStatus.NEW
    )
    consecutive_failures = models.PositiveIntegerField(default=0)
    consecutive_successes = models.PositiveIntegerField(default=0)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    # No model-level default on purpose: "now()" is a business decision made
    # once, at creation time, by apps.monitors.services.create_monitor — not
    # a passive field default that would also fire on, say, a data migration.
    next_check_at = models.DateTimeField()

    class Meta:
        indexes = [
            # The dispatcher's hot path: "which enabled monitors
            # are due right now" — see ARCHITECTURE.md §6.2.
            models.Index(fields=["is_enabled", "next_check_at"], name="monitor_dispatch_idx"),
            # A user's own monitor list, newest first — the only query the
            # API itself runs against this table in this chunk.
            models.Index(fields=["user", "created_at"], name="monitor_user_created_idx"),
        ]
        constraints = [
            CheckConstraint(
                condition=Q(expected_status__gte=100) & Q(expected_status__lte=599),
                name="monitor_expected_status_range",
            ),
            CheckConstraint(
                condition=Q(timeout_seconds__gte=1) & Q(timeout_seconds__lte=30),
                name="monitor_timeout_range",
            ),
            CheckConstraint(
                condition=Q(failure_threshold__gte=1) & Q(failure_threshold__lte=10),
                name="monitor_failure_threshold_range",
            ),
            CheckConstraint(
                condition=Q(success_threshold__gte=1) & Q(success_threshold__lte=10),
                name="monitor_success_threshold_range",
            ),
            # Redundant with the ranges above given the current ALLOWED_INTERVALS
            # (max timeout 30 < min interval 60), but it documents the actual
            # invariant ("иначе проверки наложатся друг на друга")
            # rather than relying on that being true by coincidence forever.
            CheckConstraint(
                condition=Q(timeout_seconds__lt=F("interval_seconds")),
                name="monitor_timeout_lt_interval",
            ),
            CheckConstraint(
                condition=Q(interval_seconds__in=ALLOWED_INTERVALS),
                name="monitor_interval_allowed_values",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.url})"

    def clean(self) -> None:
        # Cross-field check — a single field's `validators=[...]` can't
        # express "timeout < interval", so it belongs in clean() instead.
        # Django Admin's ModelForm calls full_clean() (and therefore this)
        # automatically; the API gets the same check via a mirrored
        # `validate()` on MonitorWriteSerializer, since DRF does not call
        # the model's clean() for you. on keeping domain rules out of the HTTP layer while still surfacing
        # them there as a normal 400.
        super().clean()
        if self.timeout_seconds is not None and self.interval_seconds is not None:
            if self.timeout_seconds >= self.interval_seconds:
                raise ValidationError(
                    {"timeout_seconds": "timeout_seconds must be less than interval_seconds."}
                )
