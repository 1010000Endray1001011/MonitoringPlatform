from django.db import models
from django.db.models import CheckConstraint, Q, UniqueConstraint


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


class MonitorHourlyStat(models.Model):
    """One hour's worth of CheckResult rows, boiled down to a single row.

    This is what makes "uptime over the last 30 days" a query over ~720
    small rows per monitor instead of a scan over however many thousands
    of raw checks happened in that window — and it's also what retention
    (purge_old_check_results) waits for before it's willing to delete the
    raw rows an hour's worth of history came from. Same reasoning as
    CheckResult for using a plain integer pk instead of a UUID: this table
    is still high-volume (one row per monitor per hour, forever), just
    ~60x smaller than the raw table it summarizes.

    avg/min/max/p95 are computed from *successful* checks only — a
    response_time_ms only exists once a response actually arrived, so
    there's nothing meaningful to average over a failed check.
    """

    monitor = models.ForeignKey(
        "monitors.Monitor", on_delete=models.CASCADE, related_name="hourly_stats"
    )
    hour_start = models.DateTimeField()
    checks_total = models.PositiveIntegerField()
    checks_failed = models.PositiveIntegerField()
    avg_response_ms = models.PositiveIntegerField(null=True, blank=True)
    min_response_ms = models.PositiveIntegerField(null=True, blank=True)
    max_response_ms = models.PositiveIntegerField(null=True, blank=True)
    # Not a true statistical percentile over the raw rows — see
    # apps/checks/domain.py's compute_response_time_stats for exactly what
    # this is instead and why that's an acceptable trade-off here.
    p95_response_ms = models.PositiveIntegerField(null=True, blank=True)
    # Seconds of this hour that overlapped an Incident touching this
    # monitor (open or since-resolved) — computed once here at rollup time
    # so the /stats endpoint never has to re-walk Incident rows itself.
    downtime_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            # Per-monitor history, newest first — what the /stats endpoint
            # actually reads.
            models.Index(fields=["monitor", "-hour_start"], name="hourlystat_monitor_idx"),
            # A plain hour_start index too, same reasoning as CheckResult's
            # own checked_at index: the retention sweep scans across every
            # monitor by hour, not by monitor first.
            models.Index(fields=["hour_start"], name="hourlystat_hour_start_idx"),
        ]
        constraints = [
            # One row per (monitor, hour) is also the idempotency mechanism
            # for the rollup task — re-running it for an hour that's
            # already aggregated does an update_or_create, never a
            # duplicate.
            UniqueConstraint(fields=["monitor", "hour_start"], name="hourlystat_unique_hour"),
        ]
        ordering = ["-hour_start"]

    def __str__(self) -> str:
        return f"{self.monitor_id} @ {self.hour_start}"
