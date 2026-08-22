import yaml
from rest_framework import status


def test_openapi_schema_generates_without_errors(api_client):
    response = api_client.get("/api/schema/")

    assert response.status_code == status.HTTP_200_OK
    schema = yaml.safe_load(response.content)
    assert schema["info"]["title"] == "Uptime Monitoring Platform API"
    assert "/api/v1/auth/register" in schema["paths"]


def test_swagger_ui_is_served(api_client):
    response = api_client.get("/api/docs/")

    assert response.status_code == status.HTTP_200_OK
