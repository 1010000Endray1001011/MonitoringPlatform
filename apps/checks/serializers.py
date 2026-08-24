from rest_framework import serializers

from .models import CheckResult


class CheckResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckResult
        fields = [
            "id",
            "checked_at",
            "success",
            "status_code",
            "response_time_ms",
            "error_type",
            "error_message",
            "response_size_bytes",
        ]
        read_only_fields = fields


class ImmediateCheckAcceptedSerializer(serializers.Serializer):
    """Shape of the 202 response from triggering an out-of-schedule check —
    there's no object to represent, just an acknowledgement and where to
    look for the result once it exists."""

    detail = serializers.CharField(read_only=True)
    poll_url = serializers.CharField(read_only=True)
