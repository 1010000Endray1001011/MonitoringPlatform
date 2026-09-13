from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from . import services
from .models import NotificationChannel


class NotificationChannelSerializer(serializers.ModelSerializer):
    telegram_deep_link = serializers.SerializerMethodField()

    class Meta:
        model = NotificationChannel
        fields = [
            "id",
            "type",
            "name",
            "config",
            "is_verified",
            "is_active",
            "telegram_deep_link",
            "last_error",
            "last_error_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_verified",
            "telegram_deep_link",
            "last_error",
            "last_error_at",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_telegram_deep_link(self, obj: NotificationChannel) -> str | None:
        """The t.me link to tap, or null when there's nothing to show —
        already connected, expired, or not a Telegram channel at all."""
        if obj.type != NotificationChannel.ChannelType.TELEGRAM:
            return None
        return services.telegram_deep_link(channel=obj)

    def validate(self, attrs: dict) -> dict:
        # Mirrors NotificationChannel.clean() so a bad config comes back as
        # a normal 400 here rather than reaching the service and failing
        # full_clean() there.
        channel_type = attrs.get("type", getattr(self.instance, "type", None))
        config = attrs.get("config", getattr(self.instance, "config", None)) or {}

        if channel_type == NotificationChannel.ChannelType.EMAIL and not config.get("email"):
            raise serializers.ValidationError({"config": "EMAIL channels require an 'email' key."})

        if channel_type == NotificationChannel.ChannelType.TELEGRAM and "config" in attrs:
            # `username` is the only key a client may set. chat_id is
            # assigned exclusively by the claim handshake, from an update
            # Telegram itself delivered — accepting one from the request
            # body would let anyone aim a channel at a stranger's chat and
            # bury them in someone else's incident alerts.
            existing = getattr(self.instance, "config", None) or {}
            new_config = {}
            username = (config.get("username") or "").lstrip("@").strip()
            if username:
                new_config["username"] = username
            if existing.get("chat_id"):
                # Editing the declared username shouldn't silently unbind a
                # chat that's already connected and working.
                new_config["chat_id"] = existing["chat_id"]
            attrs["config"] = new_config

        return attrs
