import os
import logging
from typing import Iterable

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration


_INITIALIZED_SERVICES: set[str] = set()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _release() -> str | None:
    for key in ("SENTRY_RELEASE", "APP_RELEASE", "GIT_SHA", "RELEASE_SHA"):
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    return None


def _environment(default_debug: bool = False) -> str:
    explicit = (os.getenv("SENTRY_ENVIRONMENT") or "").strip()
    if explicit:
        return explicit
    return "development" if default_debug else "production"


def _integrations(enable_django: bool, enable_celery: bool) -> Iterable[object]:
    integrations: list[object] = [
        LoggingIntegration(
            level=None,
            event_level=logging.ERROR,
        )
    ]
    if enable_django:
        integrations.append(DjangoIntegration())
    if enable_celery:
        integrations.append(CeleryIntegration())
    return integrations


def init_sentry(*, service_name: str, enable_django: bool = False, enable_celery: bool = False) -> bool:
    dsn = (os.getenv("SENTRY_DSN") or "").strip()
    if not dsn:
        return False
    if service_name in _INITIALIZED_SERVICES:
        return True

    debug = _env_bool("DEBUG", False)
    sentry_sdk.init(
        dsn=dsn,
        environment=_environment(default_debug=debug),
        release=_release(),
        server_name=service_name,
        send_default_pii=_env_bool("SENTRY_SEND_DEFAULT_PII", True),
        traces_sample_rate=_env_float("SENTRY_TRACES_SAMPLE_RATE", 0.0),
        profiles_sample_rate=_env_float("SENTRY_PROFILES_SAMPLE_RATE", 0.0),
        integrations=list(_integrations(enable_django=enable_django, enable_celery=enable_celery)),
        max_request_body_size=os.getenv("SENTRY_MAX_REQUEST_BODY_SIZE", "medium"),
    )
    _INITIALIZED_SERVICES.add(service_name)
    return True
