from django.db import models
from django.db.models import CheckConstraint, Q


class CheckResult(models.Model):
    """One HTTP probe attempt, recorded exactly as it happened.

    Append-only: nothing ever updates a row here once it's written, and
    that's deliberate — this table is the raw history a monitor's uptime
    and incidents get computed from, so its rows have to stay a faithful
    record of "what did we actually observe" rather than being touched up
    after the fact. Deletion is fine (it's how old rows eventually get
    trimmed), editing is not.

    Uses a plain auto-incrementing integer id instead of a UUID on purpose:
    this table is going to hold by far the most rows of anything in the
    system (one row per check, every interval, forever until trimmed), and
    a bigint primary key keeps every index on it meaningfully smaller than
    a UUID one would.

    Deliberately absent: the response body and response headers. A monitor
    points at whatever URL its owner configured, which the platform has no
    control over — logging the body would mean silently capturing whatever
    that endpoint chooses to return, personal data and secrets included.
    Only metadata about the response is kept, never its content.
    """

    class ErrorType(models.TextChoices):
        DNS_ERROR = "DNS_ERROR", "DNS error"
        CONNECTION_REFUSED = "CONNECTION_REFUSED", "Connection refused"
        CONNECTION_ERROR = "CONNECTION_ERROR", "Connection error"
        TIMEOUT = "TIMEOUT", "Timeout"
        SSL_ERROR = "SSL_ERROR", "SSL error"
        TOO_MANY_REDIRECTS = "TOO_MANY_REDIRECTS", "Too many redirects"
        RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE", "Response too large"
        UNEXPECTED_STATUS = "UNEXPECTED_STATUS", "Unexpected status"
        BLOCKED_TARGET = "BLOCKED_TARGET", "Blocked target"
        INTERNAL_ERROR = "INTERNAL_ERROR", "Internal error"

    monitor = models.ForeignKey(
        "monitors.Monitor", on_delete=models.CASCADE, related_name="check_results"
    )
    # The moment the probe *started*, not the moment this row was written —
    # those can differ by however long the request itself took, and the
    # start time is what makes a series of rows line up into an accurate
    # timeline. Set explicitly by the code that ran the probe rather than
    # auto_now_add, since "now" at insert time is the wrong instant.
    checked_at = models.DateTimeField()
    success = models.BooleanField()
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    # null=True is usually wrong on a CharField (it creates two different
    # "empty" values, "" and NULL) — but this field has `choices`, and ""
    # isn't a member of ErrorType. None unambiguously means "not
    # applicable" here instead of colliding with a real, if empty, choice.
    error_type = models.CharField(  # noqa: DJ001
        max_length=20, choices=ErrorType.choices, null=True, blank=True
    )
    # Truncated technical detail for diagnosis, not a place for anything
    # from the response itself — see the "deliberately absent" note above.
    # null=True for the same reason as error_type: this is only ever set
    # together with it, so the two should be nullable/not-nullable the same
    # way rather than one using "" as its "nothing to report" value.
    error_message = models.CharField(max_length=500, null=True, blank=True)  # noqa: DJ001
    response_size_bytes = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        indexes = [
            # The read path this whole table exists for: "show me this
            # monitor's recent history", newest first.
            models.Index(fields=["monitor", "-checked_at"], name="checkresult_monitor_idx"),
            # Supports the future retention sweep ("delete everything older
            # than N days") without a full table scan.
            models.Index(fields=["checked_at"], name="checkresult_checked_at_idx"),
        ]
        constraints = [
            # A successful check has nothing to explain; a failed one always
            # does — expressed here so the two fields can't quietly drift
            # out of sync no matter what code path writes a row.
            CheckConstraint(
                condition=(
                    Q(success=True, error_type__isnull=True)
                    | Q(success=False, error_type__isnull=False)
                ),
                name="checkresult_success_matches_error_type",
            ),
        ]
        ordering = ["-checked_at"]

    def __str__(self) -> str:
        outcome = "OK" if self.success else (self.error_type or "FAILED")
        return f"{self.monitor_id} @ {self.checked_at}: {outcome}"
