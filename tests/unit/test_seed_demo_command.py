import pytest
from django.core.management import call_command

from apps.accounts.models import User
from apps.monitors.models import Monitor

pytestmark = pytest.mark.django_db


def test_creates_a_demo_user_and_two_monitors():
    call_command("seed_demo")

    user = User.objects.get(email="demo@example.com")
    assert user.check_password("Demo-Pass123!")
    assert Monitor.objects.filter(user=user).count() == 2


def test_the_failing_monitor_cannot_actually_pass():
    call_command("seed_demo")

    failing = Monitor.objects.get(name="Demo — guaranteed failing")
    # example.com reliably answers 200 — a monitor that only accepts 404
    # can never see a matching status, by construction, with no dependency
    # on any third-party "always broken" endpoint staying that way.
    assert failing.expected_status == 404


def test_running_it_twice_does_not_duplicate_anything():
    call_command("seed_demo")
    call_command("seed_demo")

    assert User.objects.filter(email="demo@example.com").count() == 1
    assert Monitor.objects.filter(user__email="demo@example.com").count() == 2
