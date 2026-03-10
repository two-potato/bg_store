import importlib.util
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured


SETTINGS_BASE_PATH = Path(__file__).resolve().parents[1] / "config" / "settings" / "base.py"


def _load_base_settings_module():
    spec = importlib.util.spec_from_file_location("settings_base_under_test", SETTINGS_BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _set_strict_prod_env(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    baseline = {
        "DEBUG": "0",
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "DJANGO_SECRET_KEY": "prod-secret-key",
        "INTERNAL_TOKEN": "prod-internal-token",
        "ORDER_APPROVE_SECRET": "prod-order-approve-secret",
        "METRICS_TOKEN": "prod-metrics-token",
        "TELEGRAM_BOT_TOKEN": "prod-telegram-token",
        "ALLOWED_HOSTS": "servio.test,www.servio.test",
        "CSRF_TRUSTED_ORIGINS": "https://servio.test,https://www.servio.test",
    }
    for key, value in {**baseline, **overrides}.items():
        monkeypatch.setenv(key, value)


def test_strict_prod_requires_explicit_non_local_csrf_origins(monkeypatch: pytest.MonkeyPatch):
    _set_strict_prod_env(monkeypatch, CSRF_TRUSTED_ORIGINS="")

    with pytest.raises(ImproperlyConfigured, match="CSRF_TRUSTED_ORIGINS must be explicitly configured"):
        _load_base_settings_module()


def test_strict_prod_rejects_weak_metrics_token(monkeypatch: pytest.MonkeyPatch):
    _set_strict_prod_env(monkeypatch, METRICS_TOKEN="change-me")

    with pytest.raises(ImproperlyConfigured, match="METRICS_TOKEN must be set to a strong value"):
        _load_base_settings_module()


def test_strict_prod_rejects_local_allowed_hosts(monkeypatch: pytest.MonkeyPatch):
    _set_strict_prod_env(monkeypatch, ALLOWED_HOSTS="servio.test,localhost")

    with pytest.raises(ImproperlyConfigured, match="ALLOWED_HOSTS must not contain localhost-only hosts"):
        _load_base_settings_module()


def test_strict_prod_accepts_https_csrf_and_parses_cors_origins(monkeypatch: pytest.MonkeyPatch):
    _set_strict_prod_env(
        monkeypatch,
        CORS_ALLOWED_ORIGINS="https://app.servio.test, https://admin.servio.test",
    )

    module = _load_base_settings_module()

    assert module.ALLOWED_HOSTS == ["servio.test", "www.servio.test"]
    assert module.CSRF_TRUSTED_ORIGINS == ["https://servio.test", "https://www.servio.test"]
    assert module.CORS_ALLOWED_ORIGINS == ["https://app.servio.test", "https://admin.servio.test"]
