from django.contrib import admin

from .models import CheckResult


@admin.register(CheckResult)
class CheckResultAdmin(admin.ModelAdmin):
    list_display = [
        "monitor",
        "checked_at",
        "success",
        "status_code",
        "error_type",
        "response_time_ms",
    ]
    list_filter = ["success", "error_type"]
    search_fields = ["monitor__name", "monitor__url"]
    date_hierarchy = "checked_at"

    # Append-only history: the admin can look, never touch. Editing a row
    # here would falsify what the monitoring engine actually observed, and
    # deleting one by hand would leave a silent gap indistinguishable from
    # a real one.
    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
