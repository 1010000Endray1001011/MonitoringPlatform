from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

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
        # apps.monitors.Monitor does not exist yet; once it
        # does, replace with an annotated queryset count instead of this stub.
        user.monitors_used = 0
        return Response(MeSerializer(user).data)
