from celery import shared_task
import logging, time
from django.conf import settings
import httpx, asyncio
from orders.models import Order
from commerce.models import LegalEntityMembership
from core.secure import sign_approve
from core.pdf import render_invoice_pdf

log = logging.getLogger("orders")

@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def notify_entity_admins_order_created(self, order_id: int):
    t0 = time.perf_counter_ns()
    log.info("task_start notify_entity_admins_order_created", extra={"order_id": order_id})
    order = Order.objects.select_related("legal_entity","delivery_address").get(id=order_id)
    admins = LegalEntityMembership.objects.filter(
        legal_entity=order.legal_entity,
        role__in=[LegalEntityMembership.Role.OWNER, LegalEntityMembership.Role.ADMIN]
    ).select_related("user__profile")
    async def send():
        async with httpx.AsyncClient(timeout=15) as c:
            for m in admins:
                tg = getattr(m.user.profile, "telegram_id", None)
                if tg:
                    await c.post(f"{settings.BOT_BASE_URL}/notify/send_kb", json={
                        "telegram_id": tg,
                        "text": f"🧾 Новый заказ #{order.id}\n{order.legal_entity.name}\nСумма: {order.total}",
                        "keyboard": [[
                            {"text":"✅ Подтвердить","callback_data":f"approve:{order.id}:{sign_approve(order.id, tg)}"},
                            {"text":"❌ Отклонить","callback_data":f"reject:{order.id}:{sign_approve(order.id, tg)}"},
                        ]]
                    })
    asyncio.run(send())
    dur = (time.perf_counter_ns() - t0) / 1_000_000
    log.info("task_done notify_entity_admins_order_created", extra={"order_id": order_id, "duration_ms": round(dur,2)})

@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def send_invoice_to_buyer(self, order_id: int):
    t0 = time.perf_counter_ns()
    log.info("task_start send_invoice_to_buyer", extra={"order_id": order_id})
    order = Order.objects.select_related("placed_by__profile").get(id=order_id)
    pdf_path, _ = render_invoice_pdf(order)
    tg = order.placed_by.profile.telegram_id
    async def send():
        async with httpx.AsyncClient(timeout=30) as c:
            await c.post(f"{settings.BOT_BASE_URL}/notify/send_document", json={
                "telegram_id": tg, "caption": f"Счёт по заказу #{order.id}", "path": pdf_path
            })
    asyncio.run(send())
    dur = (time.perf_counter_ns() - t0) / 1_000_000
    log.info("task_done send_invoice_to_buyer", extra={"order_id": order_id, "duration_ms": round(dur,2)})
