import pytest

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
