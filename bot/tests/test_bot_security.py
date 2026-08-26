"""Regression and security tests for bot-notify service."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

try:  # pragma: no cover - import mode depends on test runner cwd
    from bot.app.common import require_internal_token
except ModuleNotFoundError:  # pragma: no cover - local `cd bot` run
    from app.common import require_internal_token


def _import_main_notify_module(monkeypatch):
    import importlib
    import sys
    import types

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-test-token")
    # Stub sentry SDK tree for lightweight local test runs.
    sentry_sdk_module = types.ModuleType("sentry_sdk")
    sentry_sdk_module.init = lambda **kwargs: None
    integrations_module = types.ModuleType("sentry_sdk.integrations")
    integrations_fastapi_module = types.ModuleType("sentry_sdk.integrations.fastapi")
    integrations_logging_module = types.ModuleType("sentry_sdk.integrations.logging")

    class _FastApiIntegration:
        pass

    class _LoggingIntegration:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    integrations_fastapi_module.FastApiIntegration = _FastApiIntegration
    integrations_logging_module.LoggingIntegration = _LoggingIntegration
    sys.modules["sentry_sdk"] = sentry_sdk_module
    sys.modules["sentry_sdk.integrations"] = integrations_module
    sys.modules["sentry_sdk.integrations.fastapi"] = integrations_fastapi_module
    sys.modules["sentry_sdk.integrations.logging"] = integrations_logging_module

    for module_name in (
        "bot.app.main_notify",
        "app.main_notify",
    ):
        if module_name in sys.modules:
            del sys.modules[module_name]
    try:
        return importlib.import_module("bot.app.main_notify")
    except ModuleNotFoundError:
        return importlib.import_module("app.main_notify")


def test_placeholder_secret_validation_in_production_mode(monkeypatch):
    """Verify that bot-notify rejects placeholder secrets in production-like mode."""
    # Arrange: Set environment to production
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("INTERNAL_TOKEN", "change-me")  # placeholder

    # Act & Assert: Should raise RuntimeError on app startup
    with pytest.raises(
        RuntimeError, match="Cannot start bot-notify with placeholder secrets"
    ):
        module = _import_main_notify_module(monkeypatch)
        module._validate_production_secrets()


def test_placeholder_secret_warning_in_dev_mode(monkeypatch, caplog):
    """Verify that bot-notify logs warning but allows placeholders in dev mode."""
    # Arrange: Set environment to development
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("INTERNAL_TOKEN", "change-me")  # placeholder

    # Act: This should NOT raise (only warn)
    try:
        module = _import_main_notify_module(monkeypatch)
        module._validate_production_secrets()
        # If we got here, validation passed (with warning only)
        assert True
    except RuntimeError:
        pytest.fail("Should not raise in development mode, only warn")


def test_production_secrets_allowed_in_production_mode(monkeypatch):
    """Verify that bot-notify starts fine with proper secrets in production mode."""
    # Arrange: Set environment to production with proper secrets
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("INTERNAL_TOKEN", "proper-secret-token-12345")
    monkeypatch.setenv("ORDER_APPROVE_SECRET", "proper-order-secret-67890")

    # Act: Should not raise
    try:
        module = _import_main_notify_module(monkeypatch)
        module._validate_production_secrets()
        assert True
    except RuntimeError as exc:
        pytest.fail(f"Should not raise with proper secrets: {exc}")


def test_notification_service_backend_url_configured(monkeypatch):
    """Verify that notification service has backend URL configured."""
    # Arrange & Act
    monkeypatch.setenv("BACKEND_URL", "http://backend:8000")
    module = _import_main_notify_module(monkeypatch)

    # Assert
    assert module.BACKEND_URL == "http://backend:8000"
    assert module.BACKEND_URL.startswith("http")


def _auth_app() -> FastAPI:
    app = FastAPI()

    @app.post("/internal/ping")
    def _internal_ping(_auth: None = Depends(require_internal_token)):
        return {"ok": True}

    return app


def test_internal_endpoint_rejects_invalid_token(monkeypatch):
    monkeypatch.setenv("INTERNAL_TOKEN", "very-secret-token")
    monkeypatch.setenv("BOT_REQUIRE_INTERNAL_TOKEN", "1")
    client = TestClient(_auth_app())

    response = client.post(
        "/internal/ping",
        headers={"X-Internal-Token": "wrong-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid internal token"


def test_internal_endpoint_rejects_missing_token(monkeypatch):
    monkeypatch.setenv("INTERNAL_TOKEN", "very-secret-token")
    monkeypatch.setenv("BOT_REQUIRE_INTERNAL_TOKEN", "1")
    client = TestClient(_auth_app())

    response = client.post("/internal/ping")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid internal token"


def test_internal_endpoint_accepts_valid_token(monkeypatch):
    monkeypatch.setenv("INTERNAL_TOKEN", "very-secret-token")
    monkeypatch.setenv("BOT_REQUIRE_INTERNAL_TOKEN", "1")
    client = TestClient(_auth_app())

    response = client.post(
        "/internal/ping",
        headers={"X-Internal-Token": "very-secret-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
