from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = "apps.notifications"
    label = "notifications"
    verbose_name = "Notifications"

    def ready(self):
        # Importing the module is what registers its @register()-decorated
        # checks; nothing here is called directly.
        from . import system_checks  # noqa: F401
