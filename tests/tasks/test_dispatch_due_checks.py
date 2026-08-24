from datetime import timedelta

import pytest
from django.utils import timezone

from apps.checks import tasks
from integrations.http_probe import FakeHttpProbe
from tests.factories import MonitorFactory

pytestmark = pytest.mark.django_db


def test_does_not_enqueue_anything_before_its_transaction_commits(monkeypatch):
    MonitorFactory(next_check_at=timezone.now() - timedelta(seconds=1))
    fake = FakeHttpProbe()
    monkeypatch.setattr(tasks, "get_http_probe", lambda: fake)

    # No django_capture_on_commit_callbacks here: a normal pytest-django
    # test runs inside a transaction that gets rolled back, never actually
    # committed — so if run_check.delay() were called directly instead of
    # through transaction.on_commit, this would still show up as a call.
    # It doesn't, which is exactly the property this is checking for.
    tasks.dispatch_due_checks()

    assert fake.calls == []


def test_enqueues_run_check_once_its_transaction_actually_commits(
    django_capture_on_commit_callbacks, monkeypatch
):
    MonitorFactory(next_check_at=timezone.now() - timedelta(seconds=1))
    fake = FakeHttpProbe()
    monkeypatch.setattr(tasks, "get_http_probe", lambda: fake)

    with django_capture_on_commit_callbacks(execute=True):
        tasks.dispatch_due_checks()

    # CELERY_TASK_ALWAYS_EAGER means run_check.delay() ran synchronously as
    # soon as the captured on_commit callback fired, so the fake probe has
    # already been called by the time this returns.
    assert len(fake.calls) == 1


def test_enqueues_one_task_per_due_monitor(django_capture_on_commit_callbacks, monkeypatch):
    for _ in range(3):
        MonitorFactory(next_check_at=timezone.now() - timedelta(seconds=1))
    fake = FakeHttpProbe()
    monkeypatch.setattr(tasks, "get_http_probe", lambda: fake)

    with django_capture_on_commit_callbacks(execute=True):
        tasks.dispatch_due_checks()

    assert len(fake.calls) == 3
