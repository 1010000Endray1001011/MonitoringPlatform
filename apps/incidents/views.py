"""
HTTP layer for Incident: read-only (list/detail) plus the one mutation a
user can make directly — acknowledging. Opening and resolving an incident
both happen from apps.checks.processor reacting to a status transition,
never from here.
"""

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.permissions import IsMonitorOwner

from . import services
from .models import Incident
from .selectors import incidents_for_user
from .serializers import IncidentDetailSerializer, IncidentListSerializer


class IncidentViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsMonitorOwner]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "monitor"]
    ordering_fields = ["started_at"]
    ordering = ["-started_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Incident.objects.none()

        # select_related: every row's nested `monitor` field would
        # otherwise be a separate query per incident on the list view.
        return incidents_for_user(self.request.user).select_related("monitor")

    def get_serializer_class(self):
        if self.action == "list":
            return IncidentListSerializer
        return IncidentDetailSerializer

    @extend_schema(request=None, responses=IncidentDetailSerializer)
    @action(detail=True, methods=["post"])
    def acknowledge(self, request: Request, pk=None) -> Response:
        incident = services.acknowledge_incident(incident=self.get_object())
        return Response(IncidentDetailSerializer(incident).data)
