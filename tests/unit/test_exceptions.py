from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404

from apps.common.exceptions import ConflictError, DomainError, domain_exception_handler


def test_domain_error_uses_its_own_code_and_message():
    exc = ConflictError("cannot acknowledge a resolved incident")

    response = domain_exception_handler(exc, context={})

    assert response.status_code == 409
    assert response.data["error"]["code"] == "conflict"
    assert response.data["error"]["message"] == "cannot acknowledge a resolved incident"


def test_domain_error_default_message_when_none_given():
    class _CustomError(DomainError):
        code = "custom"
        status_code = 422
        default_message = "Something specific went wrong."

    response = domain_exception_handler(_CustomError(), context={})

    assert response.data["error"]["message"] == "Something specific went wrong."


def test_django_http404_is_reported_as_not_found_with_a_real_message():
    # This is exactly what a malformed UUID in a URL path produces (e.g.
    # GET /api/v1/monitors/not-a-uuid/): Django's own URL resolver raises a
    # bare Http404 with no args, which — without translating it the same
    # way DRF's own exception_handler does internally — used to fall
    # through to the generic {"code": "error", "message": ""} branch below.
    response = domain_exception_handler(Http404(), context={})

    assert response.status_code == 404
    assert response.data["error"]["code"] == "not_found"
    assert response.data["error"]["message"] == "Not found."


def test_django_permission_denied_is_reported_as_permission_denied():
    response = domain_exception_handler(DjangoPermissionDenied(), context={})

    assert response.status_code == 403
    assert response.data["error"]["code"] == "permission_denied"
