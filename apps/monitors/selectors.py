"""
Read-side queries for Monitor.

`selectors.py` exists specifically so there is exactly one place that scopes
Monitor rows by owner. Every view and service that needs more than a single
already-known Monitor instance should start from `monitors_for_user`, never
`Monitor.objects.all()` — that's what turns "don't leak other users' data"
from a rule every call site has to remember into a single choke point.

"""

from django.db.models import QuerySet

from .models import Monitor


def monitors_for_user(user) -> QuerySet[Monitor]:
    return Monitor.objects.filter(user=user)
