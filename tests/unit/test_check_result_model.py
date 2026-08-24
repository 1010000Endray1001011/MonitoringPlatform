from datetime import datetime
from datetime import timezone as dt_timezone

from apps.checks.models import CheckResult

_SOME_MONITOR_ID = "11111111-1111-1111-1111-111111111111"
_SOME_TIME = datetime(2026, 1, 1, tzinfo=dt_timezone.utc)


def test_str_shows_ok_for_a_successful_check():
    result = CheckResult(monitor_id=_SOME_MONITOR_ID, checked_at=_SOME_TIME, success=True)

    assert "OK" in str(result)


def test_str_shows_the_error_type_for_a_failed_check():
    result = CheckResult(
        monitor_id=_SOME_MONITOR_ID,
        checked_at=_SOME_TIME,
        success=False,
        error_type=CheckResult.ErrorType.TIMEOUT,
    )

    assert "TIMEOUT" in str(result)
