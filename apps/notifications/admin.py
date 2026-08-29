from django.contrib import admin

from .models import NotificationChannel, NotificationDelivery


@admin.register(NotificationChannel)
class NotificationChannelAdmin(admin.ModelAdmin):
    list_display = ["name", "type", "user", "is_verified", "is_active"]
    list_filter = ["type", "is_verified", "is_active"]
    search_fields = ["name", "user__email"]
    autocomplete_fields = ["user"]
    filter_horizontal = ["monitors"]
    # Engine-owned: only apps.notifications.services (verify_channel,
    # attempt_delivery) writes these — an admin edit could mark a channel
    # verified without ever actually having sent it a real message.
    readonly_fields = ["is_verified", "last_error", "last_error_at", "created_at", "updated_at"]


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = ["channel", "incident", "event_type", "status", "attempts", "sent_at"]
    list_filter = ["status", "event_type"]
    search_fields = ["channel__name", "incident__monitor__name"]
    date_hierarchy = "created_at"

    # Outbox / audit log, same reasoning as CheckResultAdmin: only
    # apps.notifications.tasks.deliver_notification should ever write here.
    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
