import pytest
from django.core import mail
from django.test.utils import override_settings

from orders.models import Order
from orders.tasks import notify_admin_order_status_email

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _run_on_commit_immediately(monkeypatch):
    monkeypatch.setattr("orders.signals.transaction.on_commit", lambda fn: fn())


def test_order_created_schedules_email_task(monkeypatch, user):
    calls = []

    def fake_delay(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("orders.signals.notify_admin_order_status_email.delay", fake_delay)

    order = Order.objects.create(placed_by=user)
    assert order.id is not None
    assert len(calls) == 1
    assert calls[0]["order_id"] == order.id
    assert calls[0]["event"] == "created"


def test_order_status_changed_schedules_email_task(monkeypatch, user):
    calls = []

    def fake_delay(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("orders.signals.notify_admin_order_status_email.delay", fake_delay)

    order = Order.objects.create(placed_by=user)
    calls.clear()

    order.status = Order.Status.DELIVERING
    order.save(update_fields=["status", "updated_at"])

    assert len(calls) == 1
    assert calls[0]["order_id"] == order.id
    assert calls[0]["event"] == "status_changed"
    assert calls[0]["previous_status"] == Order.Status.NEW


def test_order_save_without_status_change_does_not_schedule(monkeypatch, user):
    calls = []

    def fake_delay(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("orders.signals.notify_admin_order_status_email.delay", fake_delay)

    order = Order.objects.create(placed_by=user)
    calls.clear()

    order.customer_name = "No status change"
    order.save(update_fields=["customer_name", "updated_at"])

    assert calls == []


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    ADMIN_NOTIFY_EMAILS=["admin@example.com"],
    DEFAULT_FROM_EMAIL="noreply@test.local",
)
def test_celery_task_sends_email_on_created_event(user):
    order = Order.objects.create(placed_by=user)
    notify_admin_order_status_email(order.id, event="created", previous_status=None)

    assert len(mail.outbox) == 1
    assert f"Новый заказ #{order.id}" in mail.outbox[0].subject
    assert "admin@example.com" in mail.outbox[0].to


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    ADMIN_NOTIFY_EMAILS=["admin@example.com"],
    DEFAULT_FROM_EMAIL="noreply@test.local",
)
def test_celery_task_sends_email_on_status_change_event(user):
    order = Order.objects.create(placed_by=user)
    order.status = Order.Status.DELIVERED
    order.save(update_fields=["status", "updated_at"])

    mail.outbox = []
    notify_admin_order_status_email(order.id, event="status_changed", previous_status=Order.Status.NEW)

    assert len(mail.outbox) == 1
    assert f"Заказ #{order.id}: статус изменен" in mail.outbox[0].subject
    assert "Было: new" in mail.outbox[0].body
    assert "Стало: Выполнен" in mail.outbox[0].body


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    ADMIN_NOTIFY_EMAILS=[],
)
def test_celery_task_skips_when_no_admin_recipients(user):
    order = Order.objects.create(placed_by=user)
    notify_admin_order_status_email(order.id, event="created", previous_status=None)
    assert len(mail.outbox) == 0
