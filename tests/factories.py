import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.accounts.models import User
from apps.checks.models import CheckResult, MonitorHourlyStat
from apps.incidents.models import Incident
from apps.monitors.models import Monitor
from apps.notifications.models import NotificationChannel


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or "TestPass123!")
        if create:
            self.save()


class MonitorFactory(DjangoModelFactory):
    class Meta:
        model = Monitor

    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Monitor {n}")
    # A plain public-looking domain, not a literal IP, so the SSRF
    # validator would accept it even if full_clean() ran — it doesn't here,
    # since DjangoModelFactory saves via the manager, same as any other
    # direct .save() call (see apps/common/validators.py's docstring: the
    # validator only fires through full_clean(), which services call but
    # bare `.save()` does not).
    url = factory.Sequence(lambda n: f"http://example{n}.com/")
    # Normally set by services.create_monitor, not by the user — but tests
    # build monitors directly rather than through that service, so this has
    # to be supplied explicitly instead of defaulting to now().
    next_check_at = factory.LazyFunction(timezone.now)


class CheckResultFactory(DjangoModelFactory):
    class Meta:
        model = CheckResult

    monitor = factory.SubFactory(MonitorFactory)
    checked_at = factory.LazyFunction(timezone.now)
    success = True
    status_code = 200
    response_time_ms = 100


class IncidentFactory(DjangoModelFactory):
    class Meta:
        model = Incident

    monitor = factory.SubFactory(MonitorFactory)
    status = Incident.Status.OPEN
    started_at = factory.LazyFunction(timezone.now)
    trigger_error_type = "TIMEOUT"
    failed_checks_count = 2


class MonitorHourlyStatFactory(DjangoModelFactory):
    class Meta:
        model = MonitorHourlyStat

    monitor = factory.SubFactory(MonitorFactory)
    hour_start = factory.LazyFunction(
        lambda: timezone.now().replace(minute=0, second=0, microsecond=0)
    )
    checks_total = 60
    checks_failed = 0
    avg_response_ms = 100
    min_response_ms = 80
    max_response_ms = 150
    p95_response_ms = 140


class NotificationChannelFactory(DjangoModelFactory):
    class Meta:
        model = NotificationChannel

    user = factory.SubFactory(UserFactory)
    type = NotificationChannel.ChannelType.EMAIL
    name = factory.Sequence(lambda n: f"Channel {n}")
    config = factory.Sequence(lambda n: {"email": f"dest{n}@example.com"})
    is_verified = True
    is_active = True
