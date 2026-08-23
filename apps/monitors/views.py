"""
HTTP layer for Monitor: translates requests <-> apps.monitors.services and
nothing else (ARCHITECTURE.md §5.2, rule 1 — no business rules here).

`/check`, `/checks`, `/stats` are not in this file: they need CheckResult
and MonitorHourlyStat, which don't exist yet.
"""

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.permissions import IsOwner

from . import services
from .filters import MonitorFilterSet
from .models import Monitor
from .selectors import monitors_for_user
from .serializers import (
    MonitorDetailSerializer,
    MonitorListSerializer,
    MonitorStatusSerializer,
    MonitorWriteSerializer,
)


class MonitorViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = MonitorFilterSet
    search_fields = ["name", "url"]
    ordering_fields = ["name", "created_at", "last_checked_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            # drf-spectacular introspects the queryset with an AnonymousUser
            # to build the OpenAPI schema, before any real request exists.
            # Filtering by AnonymousUser (whose id isn't a valid Monitor.user
            # UUID) would blow up schema generation — an empty queryset is
            # enough for introspection and is never used to serve a request.
            return Monitor.objects.none()

        # The one place every request gets scoped to its owner. IsOwner
        # (above) is a second, independent check on top of this for detail
        # routes — not a substitute for it. See apps/common/permissions.py.
        return monitors_for_user(self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return MonitorListSerializer
        if self.action in ("create", "update", "partial_update"):
            return MonitorWriteSerializer
        return MonitorDetailSerializer

    @extend_schema(responses=MonitorDetailSerializer)
    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Deliberately not `serializer.save()` — creation is a service call
        # (quota check, next_check_at, full_clean), not a bare ORM insert.
        monitor = services.create_monitor(user=request.user, **serializer.validated_data)
        return Response(MonitorDetailSerializer(monitor).data, status=201)

    @extend_schema(responses=MonitorDetailSerializer)
    def update(self, request: Request, *args, **kwargs) -> Response:
        partial = kwargs.pop("partial", False)
        monitor = self.get_object()
        serializer = self.get_serializer(monitor, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        monitor = services.update_monitor(monitor=monitor, **serializer.validated_data)
        return Response(MonitorDetailSerializer(monitor).data)

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        services.delete_monitor(monitor=self.get_object())
        return Response(status=204)

    @extend_schema(request=None, responses=MonitorStatusSerializer)
    @action(detail=True, methods=["post"])
    def pause(self, request: Request, pk=None) -> Response:
        monitor = services.pause_monitor(monitor=self.get_object())
        return Response(MonitorStatusSerializer(monitor).data)

    @extend_schema(request=None, responses=MonitorStatusSerializer)
    @action(detail=True, methods=["post"])
    def resume(self, request: Request, pk=None) -> Response:
        monitor = services.resume_monitor(monitor=self.get_object())
        return Response(MonitorStatusSerializer(monitor).data)
