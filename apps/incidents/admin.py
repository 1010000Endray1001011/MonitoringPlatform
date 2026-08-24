from django.contrib import admin
from django.utils import timezone

from . import services
from .models import Incident


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ["monitor", "status", "started_at", "resolved_at", "duration_seconds"]
    list_filter = ["status", "resolution_source"]
    search_fields = ["monitor__name", "monitor__url"]
    date_hierarchy = "started_at"
    actions = ["force_resolve", "force_acknowledge"]

    # The form itself stays fully read-only — the only sanctioned way to
    # change an Incident is through apps.incidents.services, either from
    # the monitoring engine reacting to a transition, or from the actions
    # below. A raw field edit here could set `status` without the matching
    # `resolved_at`/`duration_seconds`, quietly breaking the invariant
    # those service functions exist to enforce. The actions still work
    # without change permission — Django's bulk actions only require view
    # permission, not change permission, to run.
    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    @admin.action(description="Force resolve selected incidents")
    def force_resolve(self, request, queryset):
        resolved = 0
        for incident in queryset.exclude(status=Incident.Status.RESOLVED):
            services.resolve_incident(
                incident=incident,
                resolved_at=timezone.now(),
                resolution_source=Incident.ResolutionSource.SYSTEM_RECONCILE,
            )
            resolved += 1
        self.message_user(request, f"Resolved {resolved} incident(s).")

    @admin.action(description="Force acknowledge selected incidents")
    def force_acknowledge(self, request, queryset):
        acknowledged = 0
        for incident in queryset.filter(status=Incident.Status.OPEN):
            services.acknowledge_incident(incident=incident)
            acknowledged += 1
        self.message_user(request, f"Acknowledged {acknowledged} incident(s).")
