import os
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model


@pytest.fixture
def user(db):
    User = get_user_model()
    u = User.objects.create_user(username="u1", password="pass", email="u1@example.com")
    return u


@pytest.fixture
def client_logged(client, user):
    client.force_login(user)
    return client


@pytest.fixture(autouse=True)
def _env_settings(settings):
    # Ensure deterministic tokens for tests
    settings.INTERNAL_TOKEN = "internal-token"
    settings.ORDER_APPROVE_SECRET = "approve-secret"
    settings.BOT_BASE_URL = "http://bot:8080"
    settings.GOOGLE_MAPS_API_KEY = ""
    os.environ.setdefault("DEBUG", "1")
    yield


@pytest.fixture
def api_client(client, user):
    from rest_framework_simplejwt.tokens import AccessToken
    token = str(AccessToken.for_user(user))
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client
