from django.conf import settings
from django.core.cache import cache
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import HealthCheckSerializer


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(responses=HealthCheckSerializer)
    def get(self, request):
        database_ok = self._check_database()
        redis_ok = self._check_cache()
        healthy = database_ok and redis_ok

        body = {
            "status": "ok" if healthy else "degraded",
            "database": "ok" if database_ok else "error",
            "redis": "ok" if redis_ok else "error",
            "version": settings.SPECTACULAR_SETTINGS["VERSION"],
        }
        return Response(body, status=200 if healthy else 503)

    @staticmethod
    def _check_database() -> bool:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception:
            return False

    @staticmethod
    def _check_cache() -> bool:
        try:
            cache.set("health_check_probe", "ok", timeout=5)
            return cache.get("health_check_probe") == "ok"
        except Exception:
            return False
