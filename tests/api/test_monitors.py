import pytest
from rest_framework import status

from apps.monitors.models import MAX_BODY_LENGTH, Monitor
from tests.factories import MonitorFactory, NotificationChannelFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_create_monitor(authenticated_client, user, settings):
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False

    response = authenticated_client.post(
        "/api/v1/monitors/",
        {"name": "Prod API", "url": "https://example.com/health"},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["status"] == "NEW"
    assert Monitor.objects.filter(user=user, name="Prod API").exists()


def test_create_post_monitor_with_a_request_body(authenticated_client, user):
    response = authenticated_client.post(
        "/api/v1/monitors/",
        {
            "name": "Prod API",
            "url": "https://example.com/health",
            "method": "POST",
            "body": '{"probe": true}',
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    monitor = Monitor.objects.get(user=user, name="Prod API")
    assert monitor.body == '{"probe": true}'

    detail = authenticated_client.get(f"/api/v1/monitors/{monitor.id}/")
    assert detail.data["body"] == '{"probe": true}'


def test_create_monitor_rejects_a_body_on_a_get_monitor(authenticated_client):
    response = authenticated_client.post(
        "/api/v1/monitors/",
        {
            "name": "Prod API",
            "url": "https://example.com/health",
            "method": "GET",
            "body": '{"probe": true}',
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "body" in response.data["error"]["details"]


def test_create_monitor_rejects_an_oversized_body(authenticated_client):
    response = authenticated_client.post(
        "/api/v1/monitors/",
        {
            "name": "Prod API",
            "url": "https://example.com/health",
            "method": "POST",
            "body": "x" * (MAX_BODY_LENGTH + 1),
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "body" in response.data["error"]["details"]


def test_detail_with_a_malformed_uuid_is_a_clean_404(authenticated_client):
    response = authenticated_client.get("/api/v1/monitors/not-a-uuid/")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.data["error"]["code"] == "not_found"


def test_create_monitor_rejects_private_url(authenticated_client, settings):
    settings.MONITORING_ALLOW_PRIVATE_TARGETS = False

    response = authenticated_client.post(
        "/api/v1/monitors/", {"name": "Bad", "url": "http://127.0.0.1/"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"]["code"] == "validation_error"


def test_create_monitor_enforces_quota(authenticated_client, user):
    user.monitor_quota = 1
    user.save(update_fields=["monitor_quota"])
    MonitorFactory(user=user)

    response = authenticated_client.post(
        "/api/v1/monitors/", {"name": "Second", "url": "https://example.com/"}, format="json"
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.data["error"]["code"] == "quota_exceeded"


def test_create_monitor_accepts_timeout_strictly_below_interval(authenticated_client):
    # The maximum individual timeout_seconds (30) is already below the
    # minimum individual interval_seconds (60), so this boundary can only
    # ever land on the "fine" side through the public API — see
    # test_monitor_write_serializer.py for the cross-field rule itself,
    # exercised directly since these ranges make it unreachable end-to-end.
    response = authenticated_client.post(
        "/api/v1/monitors/",
        {
            "name": "Fine timing",
            "url": "https://example.com/",
            "interval_seconds": 60,
            "timeout_seconds": 30,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED


def test_list_monitors_only_returns_the_caller_s_own(authenticated_client, user):
    MonitorFactory(user=user)
    MonitorFactory(user=UserFactory())  # someone else's monitor

    response = authenticated_client.get("/api/v1/monitors/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1


@pytest.mark.parametrize(
    "make_request",
    [
        lambda client, monitor_id: client.get(f"/api/v1/monitors/{monitor_id}/"),
        lambda client, monitor_id: client.patch(
            f"/api/v1/monitors/{monitor_id}/", {"name": "Hijacked"}, format="json"
        ),
        lambda client, monitor_id: client.delete(f"/api/v1/monitors/{monitor_id}/"),
        lambda client, monitor_id: client.post(f"/api/v1/monitors/{monitor_id}/pause/"),
        lambda client, monitor_id: client.post(f"/api/v1/monitors/{monitor_id}/resume/"),
    ],
    ids=["get", "patch", "delete", "pause", "resume"],
)
def test_other_users_monitor_is_never_visible(authenticated_client, make_request):
    # A single parametrized test rather than five near-identical ones — the
    # mismatched ownership -> 404, not 403,
    # so we never confirm another user's object even exists) applies
    # identically to every route on this resource.
    other_monitor = MonitorFactory(user=UserFactory())

    response = make_request(authenticated_client, other_monitor.id)

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_patch_cannot_change_engine_owned_fields(authenticated_client, user):
    monitor = MonitorFactory(user=user, health_status=Monitor.HealthStatus.UP)

    response = authenticated_client.patch(
        f"/api/v1/monitors/{monitor.id}/", {"health_status": "DOWN"}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    monitor.refresh_from_db()
    assert monitor.health_status == Monitor.HealthStatus.UP  # silently ignored, not an error


def test_pause_then_resume(authenticated_client, user):
    monitor = MonitorFactory(user=user, is_enabled=True)

    pause_response = authenticated_client.post(f"/api/v1/monitors/{monitor.id}/pause/")
    assert pause_response.status_code == status.HTTP_200_OK
    assert pause_response.data["status"] == "PAUSED"

    resume_response = authenticated_client.post(f"/api/v1/monitors/{monitor.id}/resume/")
    assert resume_response.status_code == status.HTTP_200_OK
    assert resume_response.data["is_enabled"] is True


def test_pause_an_already_paused_monitor_returns_409(authenticated_client, user):
    monitor = MonitorFactory(user=user, is_enabled=False)

    response = authenticated_client.post(f"/api/v1/monitors/{monitor.id}/pause/")

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["error"]["code"] == "conflict"


def test_delete_monitor(authenticated_client, user):
    monitor = MonitorFactory(user=user)

    response = authenticated_client.delete(f"/api/v1/monitors/{monitor.id}/")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Monitor.objects.filter(id=monitor.id).exists()


def test_filter_by_status_paused(authenticated_client, user):
    MonitorFactory(user=user, is_enabled=False)
    MonitorFactory(user=user, is_enabled=True, health_status=Monitor.HealthStatus.UP)

    response = authenticated_client.get("/api/v1/monitors/?status=PAUSED")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["status"] == "PAUSED"


def test_filter_by_status_health_value(authenticated_client, user):
    MonitorFactory(user=user, is_enabled=True, health_status=Monitor.HealthStatus.DOWN)
    MonitorFactory(user=user, is_enabled=True, health_status=Monitor.HealthStatus.UP)
    MonitorFactory(user=user, is_enabled=False, health_status=Monitor.HealthStatus.DOWN)

    response = authenticated_client.get("/api/v1/monitors/?status=DOWN")

    # Must match is_enabled=True AND health_status=DOWN — the paused-but
    # -formerly-DOWN monitor above is excluded, since its client-facing
    # status is PAUSED, not DOWN (apps/monitors/filters.py).
    assert response.data["count"] == 1
    assert response.data["results"][0]["status"] == "DOWN"


def test_filter_by_unrecognised_status_matches_nothing(authenticated_client, user):
    MonitorFactory(user=user)

    response = authenticated_client.get("/api/v1/monitors/?status=NOT_A_REAL_STATUS")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 0


def test_search_by_name(authenticated_client, user):
    MonitorFactory(user=user, name="Production API")
    MonitorFactory(user=user, name="Staging")

    response = authenticated_client.get("/api/v1/monitors/?search=Production")

    assert response.data["count"] == 1


def test_unauthenticated_request_is_rejected(api_client):
    response = api_client.get("/api/v1/monitors/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_create_monitor_attaches_the_caller_s_own_notification_channel(authenticated_client, user):
    channel = NotificationChannelFactory(user=user)

    response = authenticated_client.post(
        "/api/v1/monitors/",
        {
            "name": "Wired up",
            "url": "https://example.com/",
            "notification_channel_ids": [str(channel.id)],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert [c["id"] for c in response.data["notification_channels"]] == [str(channel.id)]


def test_create_monitor_rejects_another_user_s_notification_channel(authenticated_client):
    other_channel = NotificationChannelFactory(user=UserFactory())

    response = authenticated_client.post(
        "/api/v1/monitors/",
        {
            "name": "Not allowed",
            "url": "https://example.com/",
            "notification_channel_ids": [str(other_channel.id)],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_update_monitor_replaces_its_notification_channels(authenticated_client, user):
    monitor = MonitorFactory(user=user)
    first = NotificationChannelFactory(user=user)
    second = NotificationChannelFactory(user=user)
    monitor.notification_channels.add(first)

    response = authenticated_client.patch(
        f"/api/v1/monitors/{monitor.id}/",
        {"notification_channel_ids": [str(second.id)]},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    channel_ids = [c["id"] for c in response.data["notification_channels"]]
    assert channel_ids == [str(second.id)]
