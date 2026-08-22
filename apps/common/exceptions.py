from rest_framework import exceptions as drf_exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class DomainError(Exception):
    code = "validation_error"
    status_code = 400
    default_message = "The request could not be completed."

    def __init__(self, message: str | None = None, details: dict | None = None):
        self.message = message or self.default_message
        self.details = details
        super().__init__(self.message)


class QuotaExceededError(DomainError):
    code = "quota_exceeded"
    status_code = 422
    default_message = "Quota exceeded."


class ConflictError(DomainError):
    code = "conflict"
    status_code = 409
    default_message = "The requested transition is not allowed from the current state."


class ServiceUnavailableError(DomainError):
    code = "service_unavailable"
    status_code = 503
    default_message = "A required dependency is currently unavailable."


_DRF_EXCEPTION_CODES: dict[type[Exception], str] = {
    drf_exceptions.ValidationError: "validation_error",
    drf_exceptions.AuthenticationFailed: "authentication_failed",
    drf_exceptions.NotAuthenticated: "authentication_failed",
    drf_exceptions.PermissionDenied: "permission_denied",
    drf_exceptions.NotFound: "not_found",
    drf_exceptions.Throttled: "throttled",
}


def _code_for(exc: Exception) -> str:
    for exc_type, code in _DRF_EXCEPTION_CODES.items():
        if isinstance(exc, exc_type):
            return code
    return "error"


def domain_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return Response(
            {"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
            status=exc.status_code,
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    code = _code_for(exc)
    details = response.data if isinstance(response.data, (dict, list)) else None
    message = (
        str(exc.detail)
        if isinstance(exc, drf_exceptions.APIException)
        and not isinstance(exc.detail, (list, dict))
        else "Validation failed." if code == "validation_error" else str(exc)
    )

    body: dict = {"error": {"code": code, "message": message, "details": details}}
    if isinstance(exc, drf_exceptions.Throttled):
        body["retry_after"] = exc.wait

    response.data = body
    return response
