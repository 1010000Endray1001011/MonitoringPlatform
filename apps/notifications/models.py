from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import UniqueConstraint

from apps.common.models import TimeStampedModel, UUIDPrimaryKeyModel


class NotificationChannel(UUIDPrimaryKeyModel, TimeStampedModel):
    """Where a user wants to be told about their monitors' incidents.

    `config`'s shape depends on `type` (an email address for EMAIL, a
    chat_id for TELEGRAM) — validated in `clean()` rather than as separate
    columns, since adding a third channel type later only means teaching
    `clean()` (and the matching provider) the new shape, not a migration.

    The M2M to Monitor lives here, not on Monitor, so that apps.monitors
    never has to import apps.notifications — the same "depend inward
    toward monitors, never outward from it" direction every other app
    already follows for its own FKs.
    """

    class ChannelType(models.TextChoices):
        EMAIL = "EMAIL", "Email"
        TELEGRAM = "TELEGRAM", "Telegram"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_channels"
    )
    monitors = models.ManyToManyField(
        "monitors.Monitor", related_name="notification_channels", blank=True
    )
    type = models.CharField(max_length=10, choices=ChannelType.choices)
    name = models.CharField(max_length=100)
    config = models.JSONField(default=dict)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    last_error_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, null=True, blank=True)  # noqa: DJ001

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.type})"

    def clean(self) -> None:
        # Belongs here rather than only in the API serializer: this is a
        # fact about what a valid NotificationChannel *is*, not just
        # about what one HTTP request happens to accept — the admin form
        # (via full_clean()) gets the same guarantee for free.
        super().clean()
        config = self.config if isinstance(self.config, dict) else {}
        if self.type == self.ChannelType.EMAIL and not config.get("email"):
            raise ValidationError({"config": "EMAIL channels require a 'email' key."})
        if self.type == self.ChannelType.TELEGRAM and not config.get("chat_id"):
            raise ValidationError({"config": "TELEGRAM channels require a 'chat_id' key."})


class NotificationDelivery(UUIDPrimaryKeyModel, TimeStampedModel):
    """One attempt (and its outcome) to tell one channel about one incident
    event — the transactional outbox that decouples "an incident just
    changed" from "a message actually went out".

    Created in the same transaction as the Incident change it's about
    (apps.checks.processor), so a rollback of one rolls back the other —
    there's no window where an incident exists but the fact that someone
    needs to be told about it doesn't. Delivery itself happens later, in
    a Celery task, and can be retried freely without ever risking a
    duplicate: the unique constraint below means asking to notify the same
    channel about the same event twice just finds the row that already
    exists instead of creating a second one.
    """

    class EventType(models.TextChoices):
        INCIDENT_OPENED = "INCIDENT_OPENED", "Incident opened"
        INCIDENT_RESOLVED = "INCIDENT_RESOLVED", "Incident resolved"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SENDING = "SENDING", "Sending"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"

    incident = models.ForeignKey(
        "incidents.Incident", on_delete=models.CASCADE, related_name="notification_deliveries"
    )
    channel = models.ForeignKey(
        NotificationChannel, on_delete=models.CASCADE, related_name="deliveries"
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, null=True, blank=True)  # noqa: DJ001

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["incident", "channel", "event_type"],
                name="notificationdelivery_unique_event",
            ),
        ]
        indexes = [
            # Ops visibility: "what's stuck / still pending", oldest first.
            models.Index(fields=["status", "created_at"], name="notifdelivery_status_idx"),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.channel_id} <- {self.incident_id} ({self.event_type}): {self.status}"
