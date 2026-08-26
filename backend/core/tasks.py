import asyncio
import logging

from celery import shared_task
from django.conf import settings

from core.notifications import apost_notify_json, is_telegram_recipient_quarantined, send_mail_message
from users.models import UserProfile

log = logging.getLogger("core.notifications")


def _admin_emails() -> list[str]:
    emails = list(getattr(settings, "ADMIN_NOTIFY_EMAILS", []) or [])
    if emails:
        return emails
    admins = getattr(settings, "ADMINS", []) or []
    return [email for _, email in admins if email]


def _admin_telegram_ids() -> list[int]:
    recipients: list[int] = []
    seen: set[int] = set()
    qs = UserProfile.objects.filter(
        role=UserProfile.Role.ADMIN,
        telegram_id__isnull=False,
    ).values_list("telegram_id", flat=True)
    for value in qs:
        if not value:
            continue
        tg_id = int(value)
        if is_telegram_recipient_quarantined(tg_id) or tg_id in seen:
            continue
        seen.add(tg_id)
        recipients.append(tg_id)
    for value in list(getattr(settings, "ADMIN_NOTIFY_TELEGRAM_IDS", []) or []):
        if not str(value).strip().lstrip("-").isdigit():
            continue
        tg_id = int(value)
        if is_telegram_recipient_quarantined(tg_id) or tg_id in seen:
            continue
        seen.add(tg_id)
        recipients.append(tg_id)
    return recipients


def _notify_contact_feedback_impl(*, name: str, phone: str, message: str, source: str) -> None:
    text = (
        "Новая заявка из формы обратной связи\n\n"
        f"Имя: {name}\n"
        f"Телефон: {phone}\n"
        f"Источник: {source}\n\n"
        f"Сообщение:\n{message}\n"
    )
    recipients = _admin_emails()
    if recipients:
        send_mail_message(
            subject="[Servio] Новая заявка с формы контактов",
            message=text,
            recipient_list=recipients,
            logger=log,
            extra={"source": source},
        )
    else:
        log.warning("contact_feedback_email_no_recipients")

    tg_text = (
        "📩 Новая заявка с формы контактов\n"
        f"Имя: {name}\n"
        f"Телефон: {phone}\n"
        f"Источник: {source}\n\n"
        f"{message}"
    )
    telegram_ids = _admin_telegram_ids()

    async def _send() -> None:
        from httpx import AsyncClient

        async with AsyncClient(timeout=10) as client:
            for tg in telegram_ids:
                await apost_notify_json(
                    client,
                    "/notify/send_text",
                    {"telegram_id": tg, "text": tg_text},
                    logger=log,
                    failure_event="contact_feedback_send_text_failed",
                    extra={"telegram_id": tg},
                )
            await apost_notify_json(
                client,
                "/notify/send_group",
                {"text": tg_text},
                logger=log,
                failure_event="contact_feedback_group_send_failed",
            )

    try:
        asyncio.run(_send())
    except Exception:
        log.exception("contact_feedback_tg_send_failed", extra={"recipients": telegram_ids})
        raise
    log.info("contact_feedback_tg_sent", extra={"recipients": telegram_ids})


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_contact_feedback(self, *, name: str, phone: str, message: str, source: str):
    _notify_contact_feedback_impl(name=name, phone=phone, message=message, source=source)
