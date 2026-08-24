"""
HTTP layer for Monitor: translates requests <-> apps.monitors.services /
apps.checks.services and nothing else — no business rules belong here.
"""

from dataclasses import asdict
from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.checks import services as checks_services
from apps.checks import stats as stats_module
from apps.checks.models import MonitorHourlyStat
from apps.checks.selectors import annotate_last_response_time, check_results_for_monitor
from apps.checks.serializers import (
    CheckResultSerializer,
    ImmediateCheckAcceptedSerializer,
    MonitorStatsSerializer,
)
from apps.common.pagination import CheckResultCursorPagination
from apps.common.permissions import IsOwner
from apps.incidents import selectors as incidents_selectors

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

# period -> (how far back, which series granularity to use)
_STATS_PERIODS = {
    "24h": (timedelta(hours=24), "hour"),
    "7d": (timedelta(days=7), "day"),
    "30d": (timedelta(days=30), "day"),
}


def _parse_bool_param(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.strip().lower() in ("true", "1", "yes")


def _parse_datetime_param(value: str | None):
    if not value:
        return None
    # A query param that doesn't parse is treated the same as one that was
    # never given, rather than a 400 — a slightly wrong `since` value just
    # means an unfiltered (larger) result instead of a hard failure over
    # what's ultimately an optional, best-effort filter.
    return parse_datetime(value)


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
        # routes — not a substitute for it.
        queryset = monitors_for_user(self.request.user)
        # Two subqueries per request instead of two queries per row:
        # without these, last_response_time_ms and open_incident_id would
        # each fire a fresh query per monitor just to render a list.
        queryset = annotate_last_response_time(queryset)
        return incidents_selectors.annotate_open_incident_id(queryset)

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
        # A monitor this fresh cannot have a CheckResult or an Incident
        # yet — no query needed to know that, unlike get_queryset()'s
        # annotations for every other response, which read real history.
        monitor.last_response_time_ms = None
        monitor.open_incident_id = None
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

    @extend_schema(responses=CheckResultSerializer(many=True))
    @action(detail=True, methods=["get"])
    def checks(self, request: Request, pk=None) -> Response:
        monitor = self.get_object()
        queryset = check_results_for_monitor(
            monitor,
            success=_parse_bool_param(request.query_params.get("success")),
            error_type=request.query_params.get("error_type") or None,
            since=_parse_datetime_param(request.query_params.get("since")),
            until=_parse_datetime_param(request.query_params.get("until")),
        )
        # A dedicated cursor paginator, not the ViewSet's own
        # pagination_class — this table is append-only and always read
        # newest-first, which is exactly the case a cursor (not a page
        # number) stays correct and cheap for as it grows without bound.
        # `view` is deliberately omitted: passing `self` here would hand
        # CursorPagination this ViewSet's own OrderingFilter/`ordering`
        # (meant for sorting *monitors* by `-created_at`), silently
        # overriding CheckResultCursorPagination.ordering with a field
        # CheckResult doesn't even have.
        paginator = CheckResultCursorPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(CheckResultSerializer(page, many=True).data)

    @extend_schema(request=None, responses=ImmediateCheckAcceptedSerializer)
    @action(detail=True, methods=["post"], url_path="check")
    def check_now(self, request: Request, pk=None) -> Response:
        monitor = self.get_object()
        # Never runs the probe inline — this only ever enqueues it. The
        # request/response cycle can't be allowed to depend on how fast (or
        # slow) some arbitrary third-party endpoint responds.
        checks_services.request_immediate_check(monitor=monitor)
        return Response(
            {
                "detail": "Check has been queued.",
                "poll_url": f"/api/v1/monitors/{monitor.id}/checks/?page_size=1",
            },
            status=202,
        )

    @extend_schema(responses=MonitorStatsSerializer)
    @action(detail=True, methods=["get"])
    def stats(self, request: Request, pk=None) -> Response:
        monitor = self.get_object()

        period = request.query_params.get("period", "24h")
        if period not in _STATS_PERIODS:
            # Unlike the /checks history filters (since/until), a bad
            # `period` isn't a narrowing that can just fall back to "no
            # filter" — it fundamentally changes what's being asked for,
            # so silently defaulting would return data for a different
            # question than the one the caller typed.
            raise serializers.ValidationError(
                {"period": f"Must be one of: {', '.join(_STATS_PERIODS)}."}
            )
        span, granularity = _STATS_PERIODS[period]

        period_to = timezone.now()
        period_from = period_to - span

        hourly_stats = list(
            MonitorHourlyStat.objects.filter(
                monitor=monitor, hour_start__gte=period_from, hour_start__lt=period_to
            )
        )
        incident_windows = incidents_selectors.incident_windows_for_monitor(
            monitor, start=period_from, end=period_to
        )

        summary = stats_module.summarize_period(
            hourly_stats, incidents_count=len(incident_windows)
        )
        series = stats_module.build_series(hourly_stats, granularity=granularity)

        return Response(
            {
                "monitor_id": monitor.id,
                "period": period,
                "period_from": period_from,
                "period_to": period_to,
                "summary": asdict(summary),
                "series": series,
            }
        )
