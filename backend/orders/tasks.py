from celery import shared_task
import logging
import time
from django.conf import settings
from django.core.mail import send_mail
import httpx
import asyncio
from orders.models import Order
from commerce.models import LegalEntityMembership
from core.secure import sign_approve
from core.pdf import render_invoice_pdf
from users.models import UserProfile

log = logging.getLogger("orders")


def _admin_recipients() -> list[str]:
    emails = list(getattr(settings, "ADMIN_NOTIFY_EMAILS", []) or [])
    if emails:
        return emails
    # Django native ADMINS fallback: [("Name", "email@example.com"), ...]
    admins = getattr(settings, "ADMINS", []) or []
    return [email for _, email in admins if email]


def _admin_telegram_recipients() -> list[int]:
    recipients: set[int] = set(getattr(settings, "ADMIN_NOTIFY_TELEGRAM_IDS", []) or [])
    qs = UserProfile.objects.filter(
        role=UserProfile.Role.ADMIN,
        telegram_id__isnull=False,
    ).values_list("telegram_id", flat=True)
    recipients.update(int(v) for v in qs if v)
    return sorted(recipients)


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


@shared_task(bind=True, max_retries=0, default_retry_delay=30)
def notify_order_status_telegram(self, order_id: int, event: str, previous_status: str | None = None):
    order = Order.objects.select_related("legal_entity", "placed_by").get(id=order_id)
    recipients = _admin_telegram_recipients()
    if not recipients:
        log.warning("order_status_tg_no_recipients", extra={"order_id": order_id, "event": event})
        return

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
                )
                resp.raise_for_status()

    try:
        asyncio.run(send())
    except Exception as exc:
        log.exception("order_status_tg_send_failed", extra={"order_id": order_id, "event": event, "recipients": recipients})
        return
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
                    })
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
        })

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
            })
    asyncio.run(send())
    dur = (time.perf_counter_ns() - t0) / 1_000_000
    log.info("task_done send_invoice_to_buyer", extra={"order_id": order_id, "duration_ms": round(dur,2)})
