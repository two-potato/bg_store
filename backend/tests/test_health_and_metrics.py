from unittest.mock import patch

from django.core.cache import cache
from django.test.utils import override_settings


def test_health(client):
    resp = client.get("/health/")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_ready_checks_database_and_cache(client, db):
    cache.set("readiness-probe", "ok", timeout=10)
    resp = client.get("/ready/")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "database": True, "cache": True}


def test_ready_returns_503_when_database_is_unavailable(client):
    with patch("core.views.system.connection.ensure_connection", side_effect=OSError("db down")):
        resp = client.get("/ready/")
    assert resp.status_code == 503
    assert resp.json()["ok"] is False
    assert resp.json()["database"] is False


def test_ready_returns_503_when_cache_is_unavailable(client, db):
    with patch("core.views.system.cache.set", side_effect=OSError("redis down")):
        resp = client.get("/ready/")
    assert resp.status_code == 503
    assert resp.json()["ok"] is False
    assert resp.json()["cache"] is False


@override_settings(DEBUG=True, METRICS_TOKEN="")
def test_metrics_public_in_debug(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert b"python_info" in resp.content


@override_settings(DEBUG=False, METRICS_TOKEN="metrics-secret")
def test_metrics_requires_token_in_non_debug(client):
    forbidden = client.get("/metrics")
    assert forbidden.status_code == 403

    ok = client.get("/metrics", HTTP_X_METRICS_TOKEN="metrics-secret")
    assert ok.status_code == 200
    assert b"python_info" in ok.content
