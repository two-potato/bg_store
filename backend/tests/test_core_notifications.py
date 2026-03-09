from django.test.utils import override_settings

from core import notifications


class _Resp:
    def __init__(self, status_code=200, text="", payload=None):
        self.status_code = status_code
        self.text = text
        self._payload = payload or {}
        self.is_error = status_code >= 400

    def json(self):
        return self._payload


class _Client:
    def __init__(self, timeout):
        self.timeout = timeout
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json, headers):
        self.calls.append((url, json, headers))
        return _Resp(payload={"ok": True})


@override_settings(BOT_NOTIFY_URL="http://notify-bot:8080", INTERNAL_TOKEN="internal-token")
def test_post_notify_json_uses_internal_headers(monkeypatch):
    client = _Client(timeout=10)
    monkeypatch.setattr(notifications.httpx, "Client", lambda timeout: client)

    ok, resp = notifications.post_notify_json("/notify/send_text", {"telegram_id": 1, "text": "hello"})

    assert ok is True
    assert resp is not None
    assert client.calls[0][0] == "http://notify-bot:8080/notify/send_text"
    assert client.calls[0][2]["X-Internal-Token"] == "internal-token"


@override_settings(BOT_NOTIFY_URL="http://notify-bot:8080")
def test_send_telegram_group_returns_false_for_invalid_json(monkeypatch):
    class _BadJsonClient(_Client):
        def post(self, url, json, headers):
            self.calls.append((url, json, headers))
            return _Resp(payload=None)

    client = _BadJsonClient(timeout=10)
    monkeypatch.setattr(notifications.httpx, "Client", lambda timeout: client)

    assert notifications.send_telegram_group("hello") is False


@override_settings(BOT_NOTIFY_URL="http://notify-bot:8080", INTERNAL_TOKEN="internal-token")
def test_send_telegram_text_quarantines_chat_not_found(monkeypatch):
    class _BadClient(_Client):
        def post(self, url, json, headers):
            self.calls.append((url, json, headers))
            return _Resp(status_code=400, text='{"detail":"Telegram server says - Bad Request: chat not found"}')

    client = _BadClient(timeout=10)
    monkeypatch.setattr(notifications.httpx, "Client", lambda timeout: client)

    assert notifications.send_telegram_text(999001, "hello") is False
    assert notifications.is_telegram_recipient_quarantined(999001) is True
