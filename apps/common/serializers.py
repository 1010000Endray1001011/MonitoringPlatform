from rest_framework import serializers

DEPENDENCY_STATUS_CHOICES = ["ok", "error"]


class HealthCheckSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "degraded"])
    database = serializers.ChoiceField(choices=DEPENDENCY_STATUS_CHOICES)
    redis = serializers.ChoiceField(choices=DEPENDENCY_STATUS_CHOICES)
    version = serializers.CharField()
