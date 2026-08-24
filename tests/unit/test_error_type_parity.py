"""
CheckResult.error_type (a Django TextChoices, storage-side) and
integrations.http_probe.types (plain string constants, network-side) have
to agree on exactly the same set of values, or some probe outcome would be
unrepresentable in the database. Nothing enforces that at import time —
this test is what actually catches the two drifting apart.
"""

from apps.checks.models import CheckResult
from integrations.http_probe.types import ALL_ERROR_TYPES


def test_check_result_error_types_match_http_probe_error_types():
    assert set(CheckResult.ErrorType.values) == ALL_ERROR_TYPES
