"""Logging helpers used across Django views, Celery tasks, and integrations.

The module solves three related problems:

1. Keep request-scoped context in async-safe `contextvars`.
2. Provide lightweight decorators/mixins for timing and dispatch logs.
3. Offer a dependency-free JSON formatter for structured logs.
"""

import logging
import time
import uuid
import contextvars
import os
from typing import Optional
import json

# Context variables are async-safe and work across threads
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
user_var: contextvars.ContextVar[str] = contextvars.ContextVar("user", default="anon")
path_var: contextvars.ContextVar[str] = contextvars.ContextVar("path", default="-")
method_var: contextvars.ContextVar[str] = contextvars.ContextVar("method", default="-")
LOG_CALLS_ENABLED = os.getenv("LOG_CALLS_ENABLED", "1") == "1"


class RequestContextFilter(logging.Filter):
    """Inject request-scoped fields into log records."""

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        record.request_id = request_id_var.get("-")
        record.user = user_var.get("anon")
        record.path = path_var.get("-")
        record.method = method_var.get("-")
        return True


def set_request_context(request, request_id_header: str = "X-Request-ID") -> str:
    """Populate request-scoped contextvars from the current HTTP request."""
    rid: Optional[str] = request.headers.get(request_id_header) or request.META.get(
        request_id_header.replace("-", "_")
    )
    if not rid:
        rid = uuid.uuid4().hex[:12]
    request_id_var.set(rid)
    user = getattr(getattr(request, "user", None), "username", None) or "anon"
    user_var.set(str(user))
    path_var.set(getattr(request, "path", "-"))
    method_var.set(getattr(request, "method", "-"))
    return rid


def clear_request_context():
    """Clear request-scoped contextvars after the response is finished."""
    request_id_var.set("-")
    user_var.set("anon")
    path_var.set("-")
    method_var.set("-")


def log_timing(logger: logging.Logger, label: str, start_ns: int, **fields):
    """Emit a structured completion log using a monotonic start timestamp."""
    dur_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
    logger.info("%s done", label, extra={"duration_ms": round(dur_ms, 2), **fields})


def log_calls(logger: Optional[logging.Logger] = None, label: Optional[str] = None):
    """Decorate a sync function with start/success/failure timing logs."""
    def _wrap(fn):
        if not LOG_CALLS_ENABLED:
            return fn
        log = logger or logging.getLogger(fn.__module__)
        name = label or fn.__name__

        def _inner(*args, **kwargs):
            start = time.perf_counter_ns()
            log.info("%s start", name)
            try:
                res = fn(*args, **kwargs)
                dur = (time.perf_counter_ns() - start) / 1_000_000
                log.info("%s ok", name, extra={"duration_ms": round(dur, 2)})
                return res
            except Exception:
                dur = (time.perf_counter_ns() - start) / 1_000_000
                log.exception("%s failed", name, extra={"duration_ms": round(dur, 2)})
                raise
        return _inner
    return _wrap


class LoggedAPIViewMixin:
    """DRF APIView mixin that logs dispatch with status and duration."""

    def dispatch(self, request, *args, **kwargs):  # type: ignore[override]
        logger = logging.getLogger(self.__class__.__module__)
        start = time.perf_counter_ns()
        try:
            response = super().dispatch(request, *args, **kwargs)  # type: ignore[misc]
            return response
        finally:
            dur = (time.perf_counter_ns() - start) / 1_000_000
            status = getattr(locals().get('response', None), 'status_code', '-')
            logger.info(
                "dispatch %s %s -> %s",
                getattr(request, 'method', ''), getattr(request, 'path', ''), status,
                extra={"duration_ms": round(dur, 2)}
            )


class LoggedViewSetMixin(LoggedAPIViewMixin):
    """Alias mixin for DRF viewsets to share the APIView dispatch logging."""
    pass


class JSONFormatter(logging.Formatter):
    """Minimal JSON formatter to avoid extra dependencies."""

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        base = {
            "ts": self.formatTime(record, "%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "user": getattr(record, "user", "anon"),
            "path": getattr(record, "path", None),
            "method": getattr(record, "method", None),
        }
        # include extras like duration_ms etc.
        for k, v in record.__dict__.items():
            if k in base or k.startswith("_"):
                continue
            # Ignore built-in record attributes
            if k in (
                "name","msg","args","levelname","levelno","pathname","filename","module",
                "exc_info","exc_text","stack_info","lineno","funcName","created","msecs","relativeCreated",
                "thread","threadName","processName","process","asctime"
            ):
                continue
            # Skip heavy or unserializable objects (e.g., Django request)
            if k in ("request",):
                continue
            try:
                json.dumps(v)
                base[k] = v
            except Exception:
                base[k] = str(v)
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(base, ensure_ascii=False)
