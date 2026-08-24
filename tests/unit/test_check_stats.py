from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from apps.checks.domain import compute_downtime_seconds, compute_response_time_stats

_H0 = datetime(2026, 1, 1, 10, tzinfo=dt_timezone.utc)
_H1 = datetime(2026, 1, 1, 11, tzinfo=dt_timezone.utc)


def test_response_time_stats_of_an_empty_list_is_all_none():
    stats = compute_response_time_stats([])

    assert stats.avg is None
    assert stats.minimum is None
    assert stats.maximum is None
    assert stats.p95 is None


def test_response_time_stats_of_a_single_value():
    stats = compute_response_time_stats([100])

    assert (stats.avg, stats.minimum, stats.maximum, stats.p95) == (100, 100, 100, 100)


def test_response_time_stats_p95_is_nearest_rank():
    stats = compute_response_time_stats(list(range(1, 101)))  # 1..100

    assert stats.avg == 50
    assert stats.minimum == 1
    assert stats.maximum == 100
    assert stats.p95 == 95


def test_response_time_stats_ignores_input_order():
    assert compute_response_time_stats([300, 100, 200]) == compute_response_time_stats(
        [100, 200, 300]
    )


def test_downtime_seconds_for_an_incident_spanning_the_whole_hour():
    windows = [(_H0 - timedelta(hours=1), _H1 + timedelta(hours=1))]

    assert compute_downtime_seconds(windows, hour_start=_H0, hour_end=_H1) == 3600


def test_downtime_seconds_for_a_still_open_incident():
    windows = [(_H0 + timedelta(minutes=30), None)]

    assert compute_downtime_seconds(windows, hour_start=_H0, hour_end=_H1) == 1800


def test_downtime_seconds_for_no_overlap():
    windows = [(_H0 - timedelta(hours=2), _H0 - timedelta(hours=1))]

    assert compute_downtime_seconds(windows, hour_start=_H0, hour_end=_H1) == 0


def test_downtime_seconds_sums_multiple_incidents():
    windows = [
        (_H0, _H0 + timedelta(minutes=10)),
        (_H0 + timedelta(minutes=50), _H1),
    ]

    assert compute_downtime_seconds(windows, hour_start=_H0, hour_end=_H1) == 600 + 600


def test_downtime_seconds_with_no_incidents_is_zero():
    assert compute_downtime_seconds([], hour_start=_H0, hour_end=_H1) == 0
