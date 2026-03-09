import pytest
from django.test.utils import override_settings

from shopfront import tasks as sf_tasks
from users.models import UserProfile

pytestmark = pytest.mark.django_db


def test_admin_emails_prefers_admin_notify_emails(settings):
    settings.ADMIN_NOTIFY_EMAILS = ["ops@example.com"]
    settings.ADMINS = [("Fallback", "fallback@example.com")]
    assert sf_tasks._admin_emails() == ["ops@example.com"]


def test_admin_emails_fallback_to_admins(settings):
    settings.ADMIN_NOTIFY_EMAILS = []
    settings.ADMINS = [("Alice", "alice@example.com"), ("Bob", "bob@example.com")]
    assert sf_tasks._admin_emails() == ["alice@example.com", "bob@example.com"]


@override_settings(ADMIN_NOTIFY_EMAILS=[], ADMIN_NOTIFY_TELEGRAM_IDS=[])
def test_notify_contact_feedback_exits_when_no_recipients(monkeypatch):
    sent = {"emails": 0}

    def _fake_send_mail_message(**kwargs):
        sent["emails"] += 1

    monkeypatch.setattr(sf_tasks, "send_mail_message", _fake_send_mail_message)

    sf_tasks.notify_contact_feedback(
        name="Ivan",
        phone="+79000000000",
        message="help",
        source="/contacts/",
    )

    assert sent["emails"] == 0


@override_settings(
    ADMIN_NOTIFY_EMAILS=["admin@example.com"],
    ADMIN_NOTIFY_TELEGRAM_IDS=[3001],
    BOT_NOTIFY_URL="http://notify-bot:8080",
)
def test_notify_contact_feedback_sends_email_and_telegram(monkeypatch, user):
    user.profile.role = UserProfile.Role.ADMIN
    user.profile.telegram_id = 1001
    user.profile.save(update_fields=["role", "telegram_id"])

    email_calls = []

    def _fake_send_mail_message(**kwargs):
        email_calls.append(kwargs)
        return True

    tg_calls = []

    class _Client:
        pass

    async def _fake_apost_notify_json(client, path, payload, **kwargs):
        tg_calls.append((path, payload, kwargs))
        return True, None

    monkeypatch.setattr(sf_tasks, "send_mail_message", _fake_send_mail_message)
    monkeypatch.setattr(sf_tasks, "apost_notify_json", _fake_apost_notify_json)

    sf_tasks.notify_contact_feedback(
        name="Ivan",
        phone="+79000000000",
        message="Нужна консультация",
        source="/contacts/",
    )

    assert len(email_calls) == 1
    assert email_calls[0]["recipient_list"] == ["admin@example.com"]
    assert len(tg_calls) == 3
    assert tg_calls[0][0] == "/notify/send_text"
    assert tg_calls[0][1]["telegram_id"] == 1001
    assert tg_calls[1][1]["telegram_id"] == 3001
    assert tg_calls[2][0] == "/notify/send_group"
