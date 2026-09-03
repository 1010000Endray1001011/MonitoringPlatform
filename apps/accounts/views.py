from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.common.throttling import FailOpenScopedRateThrottle
from apps.monitors.selectors import monitors_for_user

from .serializers import AccessTokenSerializer, MeSerializer, RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=201)


class LogoutView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=None,
        responses={204: None},
        description=(
            "Clears the refresh-token cookie. There is no server-side token "
            "blacklist (see the access/refresh token design), so an access token "
            "already handed out stays valid until it expires on its own — this "
            "only stops it from being silently renewed on this browser."
        ),
    )
    def post(self, request: Request) -> Response:
        response = Response(status=204)
        response.delete_cookie(settings.JWT_REFRESH_COOKIE_NAME, path="/api/v1/auth/")
        return response


class MeView(APIView):
    @extend_schema(responses=MeSerializer)
    def get(self, request: Request) -> Response:
        user = request.user
        # Not a stored field on User — a plain count query is cheap enough
        # here since this view only ever serves a single user, unlike a
        # list endpoint where the same pattern per-row would be a problem.
        user.monitors_used = monitors_for_user(user).count()
        return Response(MeSerializer(user).data)


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """
    The one place that writes the refresh-token cookie, used by both views
    below. `path` scopes the cookie to only the auth endpoints — the
    browser won't attach it to, say, every `/api/v1/monitors/` request,
    which is both unnecessary (those calls use the access token, sent as a
    header, not a cookie) and a smaller CSRF surface than a site-wide cookie
    would be.
    """
    response.set_cookie(
        key=settings.JWT_REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.JWT_REFRESH_COOKIE_SECURE,
        samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
        path="/api/v1/auth/",
    )


class CookieTokenObtainPairView(TokenObtainPairView):
    # A tighter, IP-keyed limit on top of the blanket anon rate — this is
    # the login endpoint, so it's the one place brute-forcing a password is
    # actually possible, and the default anon rate alone (20/min) is too
    # generous for that specifically.
    throttle_classes = [FailOpenScopedRateThrottle]
    throttle_scope = "auth_token"

    @extend_schema(
        responses=AccessTokenSerializer,
        description=(
            "Returns only the access token in the body. The refresh token is set "
            "as an httpOnly cookie (see Set-Cookie), never exposed to page "
            "JavaScript."
        ),
    )
    def post(self, request: Request, *args, **kwargs) -> Response:
        # Not calling super().post() — it would put the refresh token in
        # the JSON body, which is exactly what this view exists to avoid.
        # Rebuilding the same two lines here is cheaper than fighting the
        # parent implementation's return value after the fact.
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0]) from exc

        refresh = serializer.validated_data.pop("refresh")
        response = Response(serializer.validated_data, status=200)
        _set_refresh_cookie(response, refresh)
        return response


class CookieTokenRefreshView(TokenRefreshView):
    # No scoped throttle here (unlike login): this endpoint is already
    # gated by possession of a valid refresh-token cookie, which an
    # anonymous brute-force attempt doesn't have — the blanket anon rate is
    # protection enough for the failure case (a missing/expired cookie).

    @extend_schema(
        request=None,
        responses=AccessTokenSerializer,
        description=(
            "No request body — the refresh token is read from the httpOnly cookie "
            "set by POST /auth/token, not from JSON. Rotation is always on, so a "
            "successful call also re-sets that cookie with a new refresh token."
        ),
    )
    def post(self, request: Request, *args, **kwargs) -> Response:
        # The refresh token comes from the httpOnly cookie, never from the
        # request body — a frontend calling this endpoint doesn't (and
        # architecturally can't, since JS never sees the cookie's value)
        # send one explicitly.
        refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if refresh is None:
            raise InvalidToken("No refresh token cookie was found.")

        serializer = self.get_serializer(data={"refresh": refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0]) from exc

        data = dict(serializer.validated_data)
        # Present only when ROTATE_REFRESH_TOKENS is on (it is) — popped
        # out the same way as in CookieTokenObtainPairView, for the same
        # reason: it belongs in the cookie, never in a response a script
        # on the page could read.
        rotated_refresh = data.pop("refresh", None)
        response = Response(data, status=200)
        if rotated_refresh is not None:
            _set_refresh_cookie(response, rotated_refresh)
        return response
