from celery import shared_task
import logging
import time
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
import httpx
import asyncio
from django.utils import timezone
from datetime import timedelta
from orders.models import Order
from catalog.models import Product
from commerce.models import SellerStore
from commerce.models import LegalEntityMembership
from core.secure import sign_approve
from core.pdf import render_invoice_pdf
from .models import FakeAcquiringPayment
from core.notifications import (
    admin_telegram_ids,
    send_telegram_bulk,
    send_telegram_group,
    send_email_notification,
)

log = logging.getLogger("orders")


def _admin_recipients() -> list[str]:
    emails = list(getattr(settings, "ADMIN_NOTIFY_EMAILS", []) or [])
    if emails:
        return emails
    # Django native ADMINS fallback: [("Name", "email@example.com"), ...]
    admins = getattr(settings, "ADMINS", []) or []
    return [email for _, email in admins if email]


def _admin_telegram_recipients() -> list[int]:
    return admin_telegram_ids()


def _buyer_emails(order: Order) -> list[str]:
    recipients = set()
    if getattr(order.placed_by, "email", None):
        recipients.add(order.placed_by.email.strip())
    profile = getattr(order.placed_by, "profile", None)
    if profile and getattr(profile, "contact_email", None):
        recipients.add(profile.contact_email.strip())
    return sorted({email for email in recipients if email})


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_admin_order_status_email(self, order_id: int, event: str, previous_status: str | None = None):
    order = Order.objects.select_related("legal_entity", "placed_by").get(id=order_id)
    recipients = _admin_recipients()
    if not recipients:
        log.warning("order_email_no_recipients", extra={"order_id": order_id, "event": event})
        return

    status_text = order.get_status_display()
    if event == "created":
        subject = f"[BG Shop] Новый заказ #{order.id}"
        body = (
            f"Создан новый заказ #{order.id}\n"
            f"Статус: {status_text}\n"
            f"Клиент: {order.placed_by}\n"
            f"Юрлицо: {order.legal_entity or '-'}\n"
            f"Сумма: {order.total}\n"
        )
    else:
        subject = f"[BG Shop] Заказ #{order.id}: статус изменен"
        body = (
            f"Заказ #{order.id}: статус изменен\n"
            f"Было: {previous_status or '-'}\n"
            f"Стало: {status_text}\n"
            f"Клиент: {order.placed_by}\n"
            f"Юрлицо: {order.legal_entity or '-'}\n"
            f"Сумма: {order.total}\n"
        )

    send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=recipients,
        fail_silently=False,
    )
    log.info("order_email_sent", extra={"order_id": order_id, "event": event, "recipients": recipients})
    buyer_recipients = _buyer_emails(order)
    if buyer_recipients:
        buyer_subject = f"PotatoFarm: заказ #{order.id}"
        buyer_body = (
            f"Статус вашего заказа #{order.id}: {status_text}\n"
            f"Сумма: {order.total}\n"
            f"Если у вас есть вопросы, ответьте на это письмо."
        )
        send_email_notification(buyer_subject, buyer_body, recipients=buyer_recipients)


@shared_task(bind=True, max_retries=0, default_retry_delay=30)
def notify_order_status_telegram(self, order_id: int, event: str, previous_status: str | None = None):
    order = Order.objects.select_related("legal_entity", "placed_by", "placed_by__profile").get(id=order_id)
    recipients = _admin_telegram_recipients()

    status_text = order.get_status_display()
    if event == "created":
        text = (
            f"🆕 Новый заказ <b>#{order.id}</b>\n"
            f"Статус: <b>{status_text}</b>\n"
            f"Клиент: {order.placed_by}\n"
            f"Юрлицо: {order.legal_entity or '-'}\n"
            f"Сумма: {order.total}"
        )
    else:
        prev_text = previous_status or "-"
        text = (
            f"🔔 Заказ <b>#{order.id}</b>: статус изменён\n"
            f"Было: <code>{prev_text}</code>\n"
            f"Стало: <b>{status_text}</b>\n"
            f"Клиент: {order.placed_by}\n"
            f"Юрлицо: {order.legal_entity or '-'}\n"
            f"Сумма: {order.total}"
        )

    async def send():
        async with httpx.AsyncClient(timeout=10) as c:
            for tg in recipients:
                resp = await c.post(
                    f"{settings.BOT_NOTIFY_URL}/notify/send_text",
                    json={"telegram_id": tg, "text": text},
                    headers=_notify_headers(),
                )
                resp.raise_for_status()

    try:
        asyncio.run(send())
    except Exception:
        log.exception("order_status_tg_send_failed", extra={"order_id": order_id, "event": event, "recipients": recipients})
        return
    # Buyer notification in Telegram when account is linked.
    buyer_tg = getattr(getattr(order.placed_by, "profile", None), "telegram_id", None)
    if buyer_tg:
        buyer_text = (
            f"📦 Обновление по заказу <b>#{order.id}</b>\n"
            f"Текущий статус: <b>{status_text}</b>\n"
            f"Сумма: {order.total}"
        )
        send_telegram_bulk(buyer_text, recipients=[int(buyer_tg)])
    log.info(
        "order_status_tg_sent",
        extra={
            "order_id": order_id,
            "event": event,
            "recipients": recipients,
            "previous_status": previous_status,
            "status": order.status,
        },
    )

@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def notify_entity_admins_order_created(self, order_id: int):
    t0 = time.perf_counter_ns()
    log.info("task_start notify_entity_admins_order_created", extra={"order_id": order_id})
    order = Order.objects.select_related("legal_entity","delivery_address").get(id=order_id)
    admins = LegalEntityMembership.objects.filter(
        legal_entity=order.legal_entity,
        role__code__in=["owner","admin"]
    ).select_related("user__profile")
    async def send():
        async with httpx.AsyncClient(timeout=15) as c:
            for m in admins:
                tg = getattr(m.user.profile, "telegram_id", None)
                if tg:
                    import time as _t
                    ts = int(_t.time())
                    await c.post(f"{settings.BOT_NOTIFY_URL}/notify/send_kb", json={
                        "telegram_id": tg,
                        "text": f"🧾 Новый заказ #{order.id}\n{order.legal_entity.name}\nСумма: {order.total}",
                        "keyboard": [[
                            {"text":"✅ Подтвердить","callback_data":f"approve:{order.id}:{ts}:{sign_approve(order.id, tg, ts)}"},
                            {"text":"❌ Отклонить","callback_data":f"reject:{order.id}:{ts}:{sign_approve(order.id, tg, ts)}"},
                        ]]
                    }, headers=_notify_headers())
    asyncio.run(send())
    # Try to notify managers group via notify-bot (if configured)
    try:
        asyncio.run(_notify_group(order_id))
    except Exception:
        pass
    dur = (time.perf_counter_ns() - t0) / 1_000_000
    log.info("task_done notify_entity_admins_order_created", extra={"order_id": order_id, "duration_ms": round(dur,2)})

async def _notify_group(order_id:int):
    order = Order.objects.select_related("legal_entity").get(id=order_id)
    async with httpx.AsyncClient(timeout=10) as c:
        await c.post(f"{settings.BOT_NOTIFY_URL}/notify/send_group", json={
            "text": f"🧾 Новый заказ #{order.id} — {order.legal_entity.name} — сумма {order.total}"
        }, headers=_notify_headers())

@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def send_invoice_to_buyer(self, order_id: int):
    t0 = time.perf_counter_ns()
    log.info("task_start send_invoice_to_buyer", extra={"order_id": order_id})
    order = Order.objects.select_related("placed_by__profile").get(id=order_id)
    pdf_path, _ = render_invoice_pdf(order)
    tg = order.placed_by.profile.telegram_id
    async def send():
        async with httpx.AsyncClient(timeout=30) as c:
            await c.post(f"{settings.BOT_NOTIFY_URL}/notify/send_document", json={
                "telegram_id": tg, "caption": f"Счёт по заказу #{order.id}", "path": pdf_path
            }, headers=_notify_headers())
    asyncio.run(send())
    dur = (time.perf_counter_ns() - t0) / 1_000_000
    log.info("task_done send_invoice_to_buyer", extra={"order_id": order_id, "duration_ms": round(dur,2)})
def _notify_headers() -> dict[str, str]:
    return {"X-Internal-Token": str(getattr(settings, "INTERNAL_TOKEN", ""))}


@shared_task(bind=True, max_retries=0, default_retry_delay=60)
def notify_new_orders_sla_breach(self):
    if not getattr(settings, "MARKETPLACE_SERVICE_ALERTS_ENABLED", True):
        return
    now = timezone.now()
    limit_minutes = int(getattr(settings, "ORDER_NEW_SLA_MINUTES", 20))
    cooldown = int(getattr(settings, "ORDER_NEW_SLA_ALERT_COOLDOWN_MINUTES", 60))
    stale_before = now - timedelta(minutes=limit_minutes)
    stale_orders = (
        Order.objects.select_related("placed_by", "legal_entity")
        .filter(status=Order.Status.NEW, created_at__lt=stale_before)
        .order_by("created_at")[:50]
    )
    for order in stale_orders:
        cache_key = f"service-alert:order-new-sla:{order.id}"
        if cache.get(cache_key):
            continue
        age_min = max(1, int((now - order.created_at).total_seconds() // 60))
        text = (
            f"⏱️ SLA: заказ <b>#{order.id}</b> слишком долго в статусе NEW\n"
            f"Возраст: {age_min} мин\n"
            f"Клиент: {order.placed_by}\n"
            f"Юрлицо: {order.legal_entity or '-'}\n"
            f"Сумма: {order.total}"
        )
        send_telegram_bulk(text)
        send_telegram_group(text)
        cache.set(cache_key, "1", timeout=cooldown * 60)
    log.info("service_alert_new_orders_checked", extra={"count": stale_orders.count()})


@shared_task(bind=True, max_retries=0, default_retry_delay=60)
def notify_low_stock_products(self):
    if not getattr(settings, "MARKETPLACE_SERVICE_ALERTS_ENABLED", True):
        return
    threshold = int(getattr(settings, "LOW_STOCK_THRESHOLD", 5))
    max_items = int(getattr(settings, "LOW_STOCK_MAX_ITEMS", 20))
    cooldown = int(getattr(settings, "LOW_STOCK_ALERT_COOLDOWN_MINUTES", 180))
    low_stock_qs = (
        Product.objects.select_related("seller", "category")
        .filter(stock_qty__lte=threshold)
        .order_by("stock_qty", "name")[: max(1, max_items * 2)]
    )
    lines = []
    for p in low_stock_qs:
        key = f"service-alert:low-stock:{p.id}"
        if cache.get(key):
            continue
        store_name = "-"
        if p.seller_id:
            store_name = (
                SellerStore.objects.filter(owner_id=p.seller_id).values_list("name", flat=True).first() or "-"
            )
        lines.append(f"• #{p.id} {p.name} | остаток: <b>{p.stock_qty}</b> | магазин: {store_name}")
        cache.set(key, "1", timeout=cooldown * 60)
        if len(lines) >= max_items:
            break
    if not lines:
        return
    text = "📉 Низкие остатки товаров:\n" + "\n".join(lines)
    send_telegram_bulk(text)
    send_telegram_group(text)
    send_email_notification("[PotatoFarm] Низкие остатки товаров", "\n".join(l.replace("<b>", "").replace("</b>", "") for l in lines))
    log.info("service_alert_low_stock_sent", extra={"items": len(lines)})


@shared_task(bind=True, max_retries=0, default_retry_delay=60)
def notify_stale_fake_payments(self):
    if not getattr(settings, "MARKETPLACE_SERVICE_ALERTS_ENABLED", True):
        return
    stale_minutes = int(getattr(settings, "FAKE_PAYMENT_STALE_MINUTES", 10))
    cooldown = int(getattr(settings, "FAKE_PAYMENT_ALERT_COOLDOWN_MINUTES", 120))
    stale_before = timezone.now() - timedelta(minutes=stale_minutes)
    payments = (
        FakeAcquiringPayment.objects.select_related("order")
        .filter(
            status__in=[FakeAcquiringPayment.Status.FAILED, FakeAcquiringPayment.Status.REQUIRES_3DS],
            created_at__lt=stale_before,
        )
        .order_by("created_at")[:50]
    )
    for pay in payments:
        key = f"service-alert:fakepay:{pay.id}:{pay.status}"
        if cache.get(key):
            continue
        text = (
            f"💳 Проблема с оплатой\n"
            f"Заказ: <b>#{pay.order_id}</b>\n"
            f"Платеж: <code>{pay.provider_payment_id}</code>\n"
            f"Статус: <b>{pay.get_status_display()}</b>\n"
            f"Сумма: {pay.amount}"
        )
        send_telegram_bulk(text)
        send_telegram_group(text)
        cache.set(key, "1", timeout=cooldown * 60)
    log.info("service_alert_fake_payment_checked", extra={"count": payments.count()})
