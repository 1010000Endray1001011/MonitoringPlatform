from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .services import register_user

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_email(self, value: str) -> str:
        normalized = value.strip().lower()
        if User.objects.filter(email=normalized).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return normalized

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data: dict) -> User:
        return register_user(email=validated_data["email"], password=validated_data["password"])


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "monitor_quota", "created_at"]
        read_only_fields = fields


class MeSerializer(serializers.ModelSerializer):
    monitors_used = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "monitor_quota", "monitors_used", "created_at"]
        read_only_fields = fields
