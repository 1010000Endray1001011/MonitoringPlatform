import pytest
from rest_framework import status

from apps.accounts.models import User

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


def test_token_obtain_pair_returns_tokens(api_client, user):
    response = api_client.post(
        "/api/v1/auth/token", {"email": user.email, "password": "TestPass123!"}
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" in response.data


def test_token_obtain_pair_rejects_invalid_credentials(api_client, user):
    response = api_client.post(
        "/api/v1/auth/token", {"email": user.email, "password": "wrong-password"}
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_token_refresh_returns_new_access_token(api_client, user):
    obtain = api_client.post(
        "/api/v1/auth/token", {"email": user.email, "password": "TestPass123!"}
    )

    response = api_client.post("/api/v1/auth/token/refresh", {"refresh": obtain.data["refresh"]})

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data


def test_me_requires_authentication(api_client):
    response = api_client.get("/api/v1/auth/me")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_me_returns_current_user(authenticated_client, user):
    response = authenticated_client.get("/api/v1/auth/me")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["email"] == user.email
    assert response.data["monitors_used"] == 0
