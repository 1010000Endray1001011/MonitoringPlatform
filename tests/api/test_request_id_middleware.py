import pytest

pytestmark = pytest.mark.django_db


def test_response_carries_a_generated_request_id(api_client):
    response = api_client.get("/health")

    assert response.headers["X-Request-ID"]


def test_response_echoes_back_a_caller_supplied_request_id(api_client):
    response = api_client.get("/health", HTTP_X_REQUEST_ID="caller-supplied-id")

    assert response.headers["X-Request-ID"] == "caller-supplied-id"
