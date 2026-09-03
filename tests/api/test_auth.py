import pytest
from django.conf import settings
from rest_framework import status

from apps.accounts.models import User
from tests.factories import MonitorFactory

pytestmark = pytest.mark.django_db


def test_register_creates_user(api_client):
    response = api_client.post(
        "/api/v1/auth/register",
        {
            "email": "Dev@Example.com",
            "password": "S0me-Str0ng-Pass",
            "password_confirm": "S0me-Str0ng-Pass",
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["email"] == "dev@example.com"
    assert User.objects.get(email="dev@example.com").check_password("S0me-Str0ng-Pass")


def test_register_duplicate_email_rejected(api_client, user):
    response = api_client.post(
        "/api/v1/auth/register",
        {
            "email": user.email,
            "password": "S0me-Str0ng-Pass",
            "password_confirm": "S0me-Str0ng-Pass",
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"]["code"] == "validation_error"


def test_register_password_mismatch_rejected(api_client):
    response = api_client.post(
        "/api/v1/auth/register",
        {
            "email": "dev@example.com",
            "password": "S0me-Str0ng-Pass",
            "password_confirm": "different",
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_register_weak_password_rejected(api_client):
    response = api_client.post(
        "/api/v1/auth/register",
        {"email": "dev@example.com", "password": "12345678", "password_confirm": "12345678"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_token_obtain_pair_returns_access_only_in_the_body(api_client, user):
    response = api_client.post(
        "/api/v1/auth/token", {"email": user.email, "password": "TestPass123!"}
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    # The refresh token must never appear where a script on the page could
    # read it — it goes out as a cookie only, checked separately below.
    assert "refresh" not in response.data


def test_token_obtain_pair_sets_an_httponly_refresh_cookie(api_client, user):
    response = api_client.post(
        "/api/v1/auth/token", {"email": user.email, "password": "TestPass123!"}
    )

    cookie = response.cookies[settings.JWT_REFRESH_COOKIE_NAME]
    assert cookie.value
    assert cookie["httponly"]
    assert cookie["samesite"] == settings.JWT_REFRESH_COOKIE_SAMESITE
    # Scoped to the auth endpoints only — see _set_refresh_cookie's comment
    # for why this isn't just "/".
    assert cookie["path"] == "/api/v1/auth/"


def test_token_obtain_pair_rejects_invalid_credentials(api_client, user):
    response = api_client.post(
        "/api/v1/auth/token", {"email": user.email, "password": "wrong-password"}
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_token_refresh_reads_the_cookie_set_by_login(api_client, user):
    # No body on the refresh call — api_client is a stateful test client
    # that carries cookies between requests the same way a browser would,
    # so the cookie login just set is what gets sent here.
    api_client.post("/api/v1/auth/token", {"email": user.email, "password": "TestPass123!"})

    response = api_client.post("/api/v1/auth/token/refresh")

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" not in response.data


def test_token_refresh_rotates_the_cookie(api_client, user):
    login = api_client.post(
        "/api/v1/auth/token", {"email": user.email, "password": "TestPass123!"}
    )
    original_refresh = login.cookies[settings.JWT_REFRESH_COOKIE_NAME].value

    response = api_client.post("/api/v1/auth/token/refresh")

    rotated_refresh = response.cookies[settings.JWT_REFRESH_COOKIE_NAME].value
    assert rotated_refresh != original_refresh


def test_token_refresh_without_a_cookie_is_rejected(api_client):
    response = api_client.post("/api/v1/auth/token/refresh")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_logout_clears_the_refresh_cookie(api_client, user):
    api_client.post("/api/v1/auth/token", {"email": user.email, "password": "TestPass123!"})

    response = api_client.post("/api/v1/auth/logout")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    cookie = response.cookies[settings.JWT_REFRESH_COOKIE_NAME]
    assert cookie.value == ""
    assert cookie["max-age"] == 0


def test_logout_works_without_being_logged_in(api_client):
    response = api_client.post("/api/v1/auth/logout")

    assert response.status_code == status.HTTP_204_NO_CONTENT


def test_me_requires_authentication(api_client):
    response = api_client.get("/api/v1/auth/me")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_me_returns_current_user(authenticated_client, user):
    response = authenticated_client.get("/api/v1/auth/me")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["email"] == user.email
    assert response.data["monitors_used"] == 0


def test_me_reflects_the_users_actual_monitor_count(authenticated_client, user):
    MonitorFactory.create_batch(3, user=user)
    MonitorFactory()  # another user's monitor — must not be counted here

    response = authenticated_client.get("/api/v1/auth/me")

    assert response.data["monitors_used"] == 3
