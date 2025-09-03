import logging
import time
from .logging_utils import set_request_context, clear_request_context


request_logger = logging.getLogger("request")


class RequestContextMiddleware:
    """Attach request context (request_id, user, path, method) to log records and responses.

    - Propagates/creates X-Request-ID
    - Ensures contextvars are set for downstream logging
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = set_request_context(request)
        try:
            response = self.get_response(request)
        finally:
            # Always add header and clear context
            try:
                response["X-Request-ID"] = rid
            except Exception:
                pass
            clear_request_context()
        return response


class RequestLoggingMiddleware:
    """Lightweight access log with timings."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter_ns()
        path = getattr(request, "path", "")
        method = getattr(request, "method", "")
        request_logger.info("%s %s", method, path)
        response = self.get_response(request)
        dur_ms = (time.perf_counter_ns() - start) / 1_000_000
        request_logger.info(
            "%s %s -> %s in %.2fms",
            method,
            path,
            getattr(response, "status_code", "-"),
            dur_ms,
        )
        return response

