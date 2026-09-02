from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.common.throttling import FailOpenScopedRateThrottle
from apps.monitors.selectors import monitors_for_user

from .serializers import MeSerializer, RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=201)


class MeView(APIView):
    @extend_schema(responses=MeSerializer)
    def get(self, request: Request) -> Response:
        user = request.user
        # Not a stored field on User — a plain count query is cheap enough
        # here since this view only ever serves a single user, unlike a
        # list endpoint where the same pattern per-row would be a problem.
        user.monitors_used = monitors_for_user(user).count()
        return Response(MeSerializer(user).data)


class ThrottledTokenObtainPairView(TokenObtainPairView):
    # A tighter, IP-keyed limit on top of the blanket anon rate — this is
    # the login endpoint, so it's the one place brute-forcing a password is
    # actually possible, and the default anon rate alone (20/min) is too
    # generous for that specifically.
    throttle_classes = [FailOpenScopedRateThrottle]
    throttle_scope = "auth_token"
