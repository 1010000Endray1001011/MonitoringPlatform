import uuid

from .logging_utils import bind_request_id, reset_request_id

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware:
    """
    Reuses an incoming X-Request-ID (set by an upstream load balancer/proxy)
    when present, otherwise mints a fresh one — either way, every log line
    produced while handling this request carries it (via
    logging_utils.RequestIDLogFilter) and it's echoed back on the response
    so a client or an operator can tie their report of "this call failed"
    to the exact server-side log lines for it.

    Placed first in MIDDLEWARE so the id is bound before any other
    middleware runs and stays bound through the whole response phase,
    including error handling further down the stack.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex
        request.request_id = request_id
        token = bind_request_id(request_id)
        try:
            response = self.get_response(request)
        finally:
            reset_request_id(token)
        response[REQUEST_ID_HEADER] = request_id
        return response
