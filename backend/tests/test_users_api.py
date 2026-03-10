import pytest
import hashlib
import hmac
import json
import time
import urllib.parse
from django.test.utils import override_settings

pytestmark = pytest.mark.django_db


def test_users_me_auth(api_client, user):
    resp = api_client.get("/api/users/me/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == user.username


def test_tg_webapp_auth_ok(monkeypatch, client):
    from users import views as users_views

    def fake_verify(init_data):
        return {"id": 123, "username": "tguser"}

    monkeypatch.setattr(users_views, "verify_init_data", fake_verify)
    resp = client.post("/api/users/auth/tg-webapp/", {"initData": "dummy"}, content_type="application/json")
    assert resp.status_code == 200
    data = resp.json()
    assert "access" in data and isinstance(data["access"], str)


def test_tg_webapp_auth_forbidden(monkeypatch, client):
    from users import views as users_views
    monkeypatch.setattr(users_views, "verify_init_data", lambda _: None)
    resp = client.post("/api/users/auth/tg-webapp/", {"initData": "bad"}, content_type="application/json")
    assert resp.status_code == 403


def _build_init_data(bot_token: str, payload: dict) -> str:
    pairs = [(k, json.dumps(v, separators=(",", ":")) if isinstance(v, dict) else str(v)) for k, v in payload.items()]
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs))
    secret_key = hashlib.sha256(f"WebAppData{bot_token}".encode()).digest()
    sig = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    pairs.append(("hash", sig))
    return urllib.parse.urlencode(pairs)


@override_settings(TELEGRAM_BOT_TOKEN="bot-token", TG_INIT_DATA_MAX_AGE_SECONDS=300)
def test_verify_init_data_rejects_expired_payload():
    from users.views import verify_init_data

    init_data = _build_init_data(
        "bot-token",
        {"auth_date": int(time.time()) - 3600, "user": {"id": 999, "username": "old"}},
    )
    assert verify_init_data(init_data) is None


@override_settings(TELEGRAM_BOT_TOKEN="bot-token", TG_INIT_DATA_MAX_AGE_SECONDS=300)
def test_verify_init_data_accepts_fresh_payload():
    from users.views import verify_init_data

    init_data = _build_init_data(
        "bot-token",
        {"auth_date": int(time.time()), "user": {"id": 123, "username": "tguser"}},
    )
    data = verify_init_data(init_data)
    assert data is not None
    assert data["id"] == 123
