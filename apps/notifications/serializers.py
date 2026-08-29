from rest_framework import serializers

from .models import NotificationChannel


class NotificationChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationChannel
        fields = [
            "id",
            "type",
            "name",
            "config",
            "is_verified",
            "is_active",
            "last_error",
            "last_error_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_verified",
            "last_error",
            "last_error_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs: dict) -> dict:
        # Mirrors NotificationChannel.clean() so a bad config comes back as
        # a normal 400 here rather than reaching the service and failing
        # full_clean() there.
        channel_type = attrs.get("type", getattr(self.instance, "type", None))
        config = attrs.get("config", getattr(self.instance, "config", None)) or {}
        if channel_type == NotificationChannel.ChannelType.EMAIL and not config.get("email"):
            raise serializers.ValidationError({"config": "EMAIL channels require an 'email' key."})
        if channel_type == NotificationChannel.ChannelType.TELEGRAM and not config.get("chat_id"):
            raise serializers.ValidationError(
                {"config": "TELEGRAM channels require a 'chat_id' key."}
            )
        return attrs
