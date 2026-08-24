"""
Pure period-summary aggregation for the /stats endpoint.

Takes already-fetched `MonitorHourlyStat` rows (and a plain
`incidents_count` int the caller already queried) and builds the
{summary, series} response shape. Zero cross-app imports on purpose, same
philosophy as apps.checks.domain: this file only ever sees values its
caller already pulled out of the database — it doesn't query anything
itself, which is what makes it trivial to unit test with hand-built rows.
"""

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class PeriodSummary:
    uptime_ratio: float | None
    checks_total: int
    checks_failed: int
    avg_response_time_ms: int | None
    p95_response_time_ms: int | None
    incidents_count: int
    total_downtime_seconds: int


def _weighted_average(rows, field_name: str) -> int | None:
    """Average `field_name` across `rows`, weighted by each row's
    successful-check count. An hour with zero successful checks has a
    `None` value for every response-time field and contributes nothing —
    weighting it in as 0 would just pull the average toward zero for no
    reason."""
    total_weight = 0
    weighted_sum = 0
    for row in rows:
        value = getattr(row, field_name)
        weight = row.checks_total - row.checks_failed
        if value is not None and weight > 0:
            total_weight += weight
            weighted_sum += value * weight
    return round(weighted_sum / total_weight) if total_weight else None


def summarize_period(hourly_stats, *, incidents_count: int) -> PeriodSummary:
    checks_total = sum(row.checks_total for row in hourly_stats)
    checks_failed = sum(row.checks_failed for row in hourly_stats)

    return PeriodSummary(
        uptime_ratio=None if checks_total == 0 else round(1 - checks_failed / checks_total, 4),
        checks_total=checks_total,
        checks_failed=checks_failed,
        avg_response_time_ms=_weighted_average(hourly_stats, "avg_response_ms"),
        # Not a statistically correct period percentile — see the module
        # docstring's reasoning. A weighted mean of the per-hour p95s
        # (same weights as the average above) is a documented
        # approximation, chosen because computing the real thing would
        # mean either keeping every raw response time for the whole
        # period, or re-querying CheckResult from scratch — exactly the
        # per-row cost the hourly rollup exists to avoid.
        p95_response_time_ms=_weighted_average(hourly_stats, "p95_response_ms"),
        incidents_count=incidents_count,
        total_downtime_seconds=sum(row.downtime_seconds for row in hourly_stats),
    )


def _bucket_row(rows) -> dict:
    return {
        "checks_total": sum(row.checks_total for row in rows),
        "checks_failed": sum(row.checks_failed for row in rows),
        "avg_response_time_ms": _weighted_average(rows, "avg_response_ms"),
        "p95_response_time_ms": _weighted_average(rows, "p95_response_ms"),
    }


def build_series(hourly_stats, *, granularity: str) -> list[dict]:
    """`granularity` is "hour" or "day". Hourly rows are already the
    finest resolution stored, so "hour" buckets are just each row passed
    through; "day" groups rows by their UTC calendar date (every
    timestamp in this system is UTC) and re-aggregates the same way
    `summarize_period` does — there's no second, database-side
    aggregation path that could drift out of sync with the first.
    """
    buckets = defaultdict(list)
    for row in hourly_stats:
        key = row.hour_start if granularity == "hour" else row.hour_start.date()
        buckets[key].append(row)

    series = []
    for bucket_key in sorted(buckets):
        series.append({"bucket": bucket_key.isoformat(), **_bucket_row(buckets[bucket_key])})
    return series
