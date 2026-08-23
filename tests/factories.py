import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.accounts.models import User
from apps.monitors.models import Monitor


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
    # Engine-owned in production (ARCHITECTURE.md §4), but tests build
    # monitors directly rather than through services.create_monitor, so
    # this has to be supplied explicitly instead of defaulting to now().
    next_check_at = factory.LazyFunction(timezone.now)
