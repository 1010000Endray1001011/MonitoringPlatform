import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from tests.factories import UserFactory


@pytest.fixture(autouse=True)
def _clear_cache():
    # DRF throttles store their request-count history in the cache backend,
    # keyed by scope + client identity. Without this, a throttle test that
    # deliberately exhausts a low rate (e.g. 5/min) would leak that history
    # into whichever test happens to run next.
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def authenticated_client(api_client: APIClient, user) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client
