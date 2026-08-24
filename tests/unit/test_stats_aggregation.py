"""
apps.checks.stats builds its {summary, series} response from already-
fetched rows — these tests hand it plain objects shaped like
MonitorHourlyStat instead of touching the database, since the function
under test never queries anything itself.
"""

from datetime import datetime
from datetime import timezone as dt_timezone
from types import SimpleNamespace

from apps.checks.stats import build_series, summarize_period


def _row(**overrides):
    defaults = dict(
        hour_start=datetime(2026, 1, 1, 10, tzinfo=dt_timezone.utc),
        checks_total=60,
        checks_failed=0,
        avg_response_ms=100,
        p95_response_ms=150,
        downtime_seconds=0,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_summarize_period_with_no_data_is_a_safe_default():
    summary = summarize_period([], incidents_count=0)

    assert summary.uptime_ratio is None
    assert summary.checks_total == 0
    assert summary.avg_response_time_ms is None


def test_summarize_period_computes_uptime_ratio():
    rows = [_row(checks_total=100, checks_failed=25)]

    summary = summarize_period(rows, incidents_count=0)

    assert summary.uptime_ratio == 0.75
    assert summary.checks_total == 100
    assert summary.checks_failed == 25


def test_summarize_period_ignores_hours_with_zero_successful_checks_in_the_average():
    rows = [
        _row(checks_total=60, checks_failed=0, avg_response_ms=100, p95_response_ms=150),
        # Every check failed this hour — nothing to average, and it must
        # not drag the weighted average toward zero.
        _row(checks_total=60, checks_failed=60, avg_response_ms=None, p95_response_ms=None),
    ]

    summary = summarize_period(rows, incidents_count=0)

    assert summary.avg_response_time_ms == 100
    assert summary.p95_response_time_ms == 150


def test_summarize_period_weights_the_average_by_successful_count():
    rows = [
        _row(checks_total=90, checks_failed=0, avg_response_ms=100),  # 90 successes @ 100ms
        _row(checks_total=10, checks_failed=0, avg_response_ms=1000),  # 10 successes @ 1000ms
    ]

    summary = summarize_period(rows, incidents_count=0)

    # (90*100 + 10*1000) / 100 = 190
    assert summary.avg_response_time_ms == 190


def test_summarize_period_sums_downtime_and_passes_through_incidents_count():
    rows = [_row(downtime_seconds=600), _row(downtime_seconds=1200)]

    summary = summarize_period(rows, incidents_count=3)

    assert summary.total_downtime_seconds == 1800
    assert summary.incidents_count == 3


def test_build_series_hour_granularity_passes_rows_through_one_bucket_each():
    rows = [
        _row(hour_start=datetime(2026, 1, 1, 10, tzinfo=dt_timezone.utc)),
        _row(hour_start=datetime(2026, 1, 1, 11, tzinfo=dt_timezone.utc)),
    ]

    series = build_series(rows, granularity="hour")

    assert [point["bucket"] for point in series] == [
        "2026-01-01T10:00:00+00:00",
        "2026-01-01T11:00:00+00:00",
    ]


def test_build_series_day_granularity_merges_hours_from_the_same_day():
    rows = [
        _row(hour_start=datetime(2026, 1, 1, 10, tzinfo=dt_timezone.utc), checks_total=60),
        _row(hour_start=datetime(2026, 1, 1, 11, tzinfo=dt_timezone.utc), checks_total=60),
        _row(hour_start=datetime(2026, 1, 2, 0, tzinfo=dt_timezone.utc), checks_total=60),
    ]

    series = build_series(rows, granularity="day")

    assert [point["bucket"] for point in series] == ["2026-01-01", "2026-01-02"]
    assert series[0]["checks_total"] == 120
    assert series[1]["checks_total"] == 60


def test_build_series_with_no_rows_is_an_empty_list():
    assert build_series([], granularity="hour") == []
