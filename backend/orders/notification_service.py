"""Formatting and recipient helpers for order-related notifications."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from orders.models import Order


@dataclass(frozen=True)
class NotificationMessage:
    """Transport-agnostic notification payload."""

    subject: str
    body: str


def admin_email_recipients() -> list[str]:
    """Resolve admin email recipients from settings or Django ADMINS."""
    emails = list(getattr(settings, "ADMIN_NOTIFY_EMAILS", []) or [])
    if emails:
        return emails
    admins = getattr(settings, "ADMINS", []) or []
    return [email for _, email in admins if email]


def buyer_email_recipients(order: Order) -> list[str]:
    """Resolve buyer-facing email recipients for a given order."""
    recipients = set()
    if order.customer_email:
        recipients.add(order.customer_email.strip())
    if getattr(order.placed_by, "email", None):
        recipients.add(order.placed_by.email.strip())
    profile = getattr(order.placed_by, "profile", None)
    if profile and getattr(profile, "contact_email", None):
        recipients.add(profile.contact_email.strip())
    return sorted({email for email in recipients if email})


def build_admin_order_email(order: Order, event: str, previous_status: str | None = None) -> NotificationMessage:
    """Build the admin-facing email payload for order events."""
    status_text = order.get_status_display()
    seller_count = max(1, order.seller_splits.count())
    if event == "created":
        return NotificationMessage(
            subject=f"[Servio] Новый заказ #{order.id}",
            body=(
                f"Создан новый заказ #{order.id}\n"
                f"Статус: {status_text}\n"
                f"Клиент: {order.buyer_display()}\n"
                f"Юрлицо: {order.legal_entity or '-'}\n"
                f"Поставщиков в заказе: {seller_count}\n"
                f"Сумма: {order.total}\n"
            ),
        )
    return NotificationMessage(
        subject=f"[Servio] Заказ #{order.id}: статус изменен",
        body=(
            f"Заказ #{order.id}: статус изменен\n"
            f"Было: {previous_status or '-'}\n"
            f"Стало: {status_text}\n"
            f"Клиент: {order.buyer_display()}\n"
            f"Юрлицо: {order.legal_entity or '-'}\n"
            f"Поставщиков в заказе: {seller_count}\n"
            f"Сумма: {order.total}\n"
        ),
    )


def build_buyer_order_email(order: Order) -> NotificationMessage:
    """Build the buyer-facing order status email payload."""
    status_text = order.get_status_display()
    return NotificationMessage(
        subject=f"Servio: заказ #{order.id}",
        body=(
            f"Статус вашего заказа #{order.id}: {status_text}\n"
            f"Сумма: {order.total}\n"
            f"Если у вас есть вопросы, ответьте на это письмо."
        ),
    )


def build_admin_order_telegram(order: Order, event: str, previous_status: str | None = None) -> str:
    """Build the admin-facing Telegram message for order events."""
    status_text = order.get_status_display()
    if event == "created":
        return (
            f"🆕 Новый заказ <b>#{order.id}</b>\n"
            f"Статус: <b>{status_text}</b>\n"
            f"Клиент: {order.buyer_display()}\n"
            f"Юрлицо: {order.legal_entity or '-'}\n"
            f"Сумма: {order.total}"
        )
    prev_text = previous_status or "-"
    return (
        f"🔔 Заказ <b>#{order.id}</b>: статус изменён\n"
        f"Было: <code>{prev_text}</code>\n"
        f"Стало: <b>{status_text}</b>\n"
        f"Клиент: {order.buyer_display()}\n"
        f"Юрлицо: {order.legal_entity or '-'}\n"
        f"Сумма: {order.total}"
    )


def build_buyer_order_telegram(order: Order) -> str:
    """Build the buyer-facing Telegram order status update."""
    status_text = order.get_status_display()
    return (
        f"📦 Обновление по заказу <b>#{order.id}</b>\n"
        f"Текущий статус: <b>{status_text}</b>\n"
        f"Сумма: {order.total}"
    )
