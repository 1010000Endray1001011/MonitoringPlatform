"""
manage.py seed_demo

One command to get from a freshly-migrated, empty database to something
worth showing someone in about two minutes: a demo account with a monitor
that's actually healthy and one that's guaranteed to fail. Goes through the
same service layer the API uses (apps.accounts.services.register_user,
apps.monitors.services.create_monitor) rather than the ORM directly, so a
seeded monitor is validated exactly the same way one created through the
API would be — including the SSRF check.

Safe to re-run: looked up by (user email) / (user, monitor name) first, so
running this against a database that already has the demo data just
reports what's already there instead of duplicating it.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.services import register_user
from apps.monitors.models import Monitor
from apps.monitors.services import create_monitor

User = get_user_model()

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "Demo-Pass123!"

# example.com is IANA-reserved specifically to stay up and stay boring —
# reliably reachable and reliably answers 200. That makes it usable for
# both monitors below: as-is for the healthy one, and with an
# impossible-to-satisfy expected_status for the failing one. Neither
# depends on some third-party "always broken" test endpoint staying alive.
DEMO_MONITORS = [
    {"name": "Demo — healthy", "url": "https://example.com/", "expected_status": 200},
    {"name": "Demo — guaranteed failing", "url": "https://example.com/", "expected_status": 404},
]


class Command(BaseCommand):
    help = "Creates a demo user with a couple of monitors for a quick end-to-end demo."

    def handle(self, *args, **options) -> None:
        user, user_created = self._get_or_create_demo_user()
        if user_created:
            self.stdout.write(self.style.SUCCESS(f"Created demo user: {DEMO_EMAIL}"))
            self.stdout.write(f"Password: {DEMO_PASSWORD}")
        else:
            self.stdout.write(f"Demo user already exists: {DEMO_EMAIL}")

        for spec in DEMO_MONITORS:
            self._get_or_create_demo_monitor(user, spec)

        self.stdout.write(
            self.style.SUCCESS(
                "Done. Log in and watch the monitors, or wait ~30s-1min for the "
                "scheduler to run their first check."
            )
        )

    def _get_or_create_demo_user(self) -> tuple[User, bool]:
        try:
            return User.objects.get(email=DEMO_EMAIL), False
        except User.DoesNotExist:
            return register_user(email=DEMO_EMAIL, password=DEMO_PASSWORD), True

    def _get_or_create_demo_monitor(self, user: User, spec: dict) -> None:
        if Monitor.objects.filter(user=user, name=spec["name"]).exists():
            self.stdout.write(f"Monitor already exists: {spec['name']}")
            return
        create_monitor(user=user, **spec)
        self.stdout.write(self.style.SUCCESS(f"Created monitor: {spec['name']}"))
