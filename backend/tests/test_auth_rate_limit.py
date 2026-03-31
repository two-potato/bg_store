import pytest
from django.core.cache import cache
from django.test import override_settings

pytestmark = pytest.mark.django_db


@override_settings(
    AUTH_LOGIN_RATE_LIMIT_ATTEMPTS=2,
    AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS=3600,
    LOGIN_CAPTCHA_THRESHOLD=999,
)
def test_login_rate_limit_returns_429_after_threshold(client):
    cache.clear()

    first = client.post("/account/login/", {"identifier": "unknown", "password": "bad"})
    second = client.post("/account/login/", {"identifier": "unknown", "password": "bad"})
    third = client.post("/account/login/", {"identifier": "unknown", "password": "bad"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert "Слишком много попыток входа" in third.content.decode("utf-8")


@override_settings(
    AUTH_REGISTER_RATE_LIMIT_ATTEMPTS=1,
    AUTH_REGISTER_RATE_LIMIT_WINDOW_SECONDS=3600,
)
def test_register_rate_limit_returns_429_after_threshold(client):
    cache.clear()

    first = client.post("/account/register/", {})
    second = client.post("/account/register/", {})

    assert first.status_code == 200
    assert second.status_code == 429
    assert "Слишком много попыток регистрации" in second.content.decode("utf-8")
