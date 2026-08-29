"""Read-side queries for NotificationChannel — the one place that scopes
channels by owner, same role as apps.monitors.selectors.monitors_for_user."""

from django.db.models import QuerySet

from .models import NotificationChannel


def channels_for_user(user) -> QuerySet[NotificationChannel]:
    return NotificationChannel.objects.filter(user=user)
