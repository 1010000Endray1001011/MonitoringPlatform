from celery import Celery
from celery.schedules import crontab

# Deliberately does NOT set DJANGO_SETTINGS_MODULE.
#
# config/__init__.py imports this module, so Python runs it before *any*
# `config.*` submodule — including config/wsgi.py. A setdefault here
# therefore won every race: gunicorn's `config.wsgi:application` would find
# the variable already set and its own setdefault("config.settings.production")
# would quietly do nothing, so the containers ran local settings — DEBUG on,
# ALLOWED_HOSTS ["*"], none of the production security headers — while the
# code read as though they ran production.
#
# Choosing the settings module belongs to whatever starts the process:
# manage.py defaults to local, wsgi/asgi default to production, and compose
# sets it explicitly for every service. Celery has no entrypoint of its own
# to do that from, so `celery -A config` needs DJANGO_SETTINGS_MODULE in the
# environment (compose provides it; see the README for running it by hand).
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
    # 5 minutes past the hour, not on the hour: gives the hour that just
    # ended a moment to fully close before summarizing it.
    "rollup-hourly-stats": {
        "task": "apps.checks.tasks.rollup_hourly_stats",
        "schedule": crontab(minute=5),
    },
    # Once a day, off-peak — this is a bulk delete over history, not
    # something that needs to run more often than the data it's trimming
    # actually grows stale.
    "purge-old-check-results": {
        "task": "apps.checks.tasks.purge_old_check_results",
        "schedule": crontab(hour=3, minute=30),
    },
    # Offset from the hourly rollup (:15 vs :05) so the two don't contend
    # over the same monitors' rows at the same moment.
    "close-stale-incidents": {
        "task": "apps.incidents.tasks.close_stale_incidents",
        "schedule": crontab(minute=15),
    },
}
