import logging
import os

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration


_INITIALIZED = False


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def init_sentry(service_name: str) -> bool:
    global _INITIALIZED
    dsn = (os.getenv("SENTRY_DSN") or "").strip()
    if not dsn or _INITIALIZED:
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=(os.getenv("SENTRY_ENVIRONMENT") or os.getenv("ENVIRONMENT") or "production").strip(),
        release=(os.getenv("SENTRY_RELEASE") or os.getenv("APP_RELEASE") or "").strip() or None,
        server_name=service_name,
        send_default_pii=(os.getenv("SENTRY_SEND_DEFAULT_PII", "1").strip().lower() in {"1", "true", "yes", "on"}),
        traces_sample_rate=_env_float("SENTRY_TRACES_SAMPLE_RATE", 0.0),
        profiles_sample_rate=_env_float("SENTRY_PROFILES_SAMPLE_RATE", 0.0),
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(level=None, event_level=logging.ERROR),
        ],
    )
    _INITIALIZED = True
    return True
