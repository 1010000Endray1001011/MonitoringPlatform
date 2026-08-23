from django.contrib import admin

from .models import Monitor


@admin.register(Monitor)
class MonitorAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "url",
        "user",
        "is_enabled",
        "health_status",
        "interval_seconds",
        "last_checked_at",
    ]
    list_filter = ["is_enabled", "health_status", "method"]
    search_fields = ["name", "url", "user__email"]
    autocomplete_fields = ["user"]

    # Everything the monitoring engine owns
    # is read-only here too — an admin editing these by hand would fight
    # the same background tasks that are supposed to own them exclusively.
    readonly_fields = [
        "health_status",
        "consecutive_failures",
        "consecutive_successes",
        "last_checked_at",
        "next_check_at",
        "created_at",
        "updated_at",
    ]
