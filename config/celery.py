import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("monitoringplatform")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # The only thing beat itself knows how to schedule — every monitor's
    # own cadence lives in Monitor.next_check_at, not here. 30 seconds is a
    # deliberate middle ground: fine-grained enough to keep the shortest
    # supported interval (60s) reasonably accurate, coarse enough not to
    # spend most of a worker's time just running this query.
    "dispatch-due-checks": {
        "task": "apps.checks.tasks.dispatch_due_checks",
        "schedule": 30.0,
    },
}
