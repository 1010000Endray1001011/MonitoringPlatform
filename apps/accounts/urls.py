from django.urls import path

from .views import (
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    LogoutView,
    MeView,
    RegisterView,
)

app_name = "accounts"

urlpatterns = [
    path("register", RegisterView.as_view(), name="register"),
    path("token", CookieTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh", CookieTokenRefreshView.as_view(), name="token_refresh"),
    path("logout", LogoutView.as_view(), name="logout"),
    path("me", MeView.as_view(), name="me"),
]
