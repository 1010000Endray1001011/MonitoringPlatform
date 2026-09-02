"""
HTTP layer for NotificationChannel: CRUD plus the one synchronous action
(verify). Delivery itself never appears here — it's driven entirely by
apps.checks.processor and the outbox, never by a user request directly.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.permissions import IsOwner

from . import services
from .models import NotificationChannel
from .selectors import channels_for_user
from .serializers import NotificationChannelSerializer


class NotificationChannelViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    serializer_class = NotificationChannelSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return NotificationChannel.objects.none()
        return channels_for_user(self.request.user)

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Deliberately not `serializer.save()` — same reasoning as
        # MonitorViewSet: creation runs through the service layer
        # (full_clean, consistent error shape), not a bare ORM insert.
        channel = services.create_channel(user=request.user, **serializer.validated_data)
        return Response(NotificationChannelSerializer(channel).data, status=201)

    def update(self, request: Request, *args, **kwargs) -> Response:
        partial = kwargs.pop("partial", False)
        channel = self.get_object()
        serializer = self.get_serializer(channel, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        channel = services.update_channel(channel=channel, **serializer.validated_data)
        return Response(NotificationChannelSerializer(channel).data)

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        services.delete_channel(channel=self.get_object())
        return Response(status=204)

    @extend_schema(
        request=None,
        responses=NotificationChannelSerializer,
        summary="Send a real test notification through this channel",
        description=(
            "Synchronous — the caller waits for the actual send attempt, unlike "
            "every other notification, which is delivered later via the outbox. "
            "On success, sets is_verified=true; only verified channels ever "
            "receive real incident notifications. On failure, the channel is "
            "returned with is_verified unchanged and last_error/last_error_at set."
        ),
    )
    @action(detail=True, methods=["post"])
    def verify(self, request: Request, pk=None) -> Response:
        # Synchronous on purpose (apps.notifications.services.verify_channel)
        # — the caller is waiting to find out whether this channel works,
        # unlike every other notification, which goes through the outbox.
        channel = services.verify_channel(channel=self.get_object())
        return Response(NotificationChannelSerializer(channel).data)
