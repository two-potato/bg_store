from celery import shared_task
import asyncio
import logging
import httpx
from django.conf import settings
from django.core.mail import send_mail
from users.models import UserProfile

log = logging.getLogger("shopfront")


def _admin_emails() -> list[str]:
    emails = list(getattr(settings, "ADMIN_NOTIFY_EMAILS", []) or [])
    if emails:
        return emails
    admins = getattr(settings, "ADMINS", []) or []
    return [email for _, email in admins if email]


def _admin_telegram_ids() -> list[int]:
    explicit = list(getattr(settings, "ADMIN_NOTIFY_TELEGRAM_IDS", []) or [])
    if explicit:
        return sorted({int(v) for v in explicit if str(v).strip().lstrip("-").isdigit()})
    recipients: set[int] = set()
    qs = UserProfile.objects.filter(
        role=UserProfile.Role.ADMIN,
        telegram_id__isnull=False,
    ).values_list("telegram_id", flat=True)
    recipients.update(int(v) for v in qs if v)
    return sorted(recipients)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_contact_feedback(self, *, name: str, phone: str, message: str, source: str):
    text = (
        "Новая заявка из формы обратной связи\n\n"
        f"Имя: {name}\n"
        f"Телефон: {phone}\n"
        f"Источник: {source}\n\n"
        f"Сообщение:\n{message}\n"
    )

    recipients = _admin_emails()
    if recipients:
        try:
            send_mail(
                subject="[BG Shop] Новая заявка с формы контактов",
                message=text,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=recipients,
                fail_silently=False,
            )
            log.info("contact_feedback_email_sent", extra={"recipients": recipients})
        except Exception:
            # Email transport issues must not block Telegram notifications.
            log.exception("contact_feedback_email_send_failed", extra={"recipients": recipients})
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

    async def _send():
        async with httpx.AsyncClient(timeout=10) as client:
            for tg in telegram_ids:
                try:
                    resp = await client.post(
                        f"{settings.BOT_NOTIFY_URL}/notify/send_text",
                        json={"telegram_id": tg, "text": tg_text},
                        headers=_notify_headers(),
                    )
                    if resp.is_error:
                        log.warning(
                            "contact_feedback_send_text_failed",
                            extra={"telegram_id": tg, "status_code": resp.status_code, "body": resp.text[:500]},
                        )
                except Exception:
                    log.exception("contact_feedback_send_text_exception", extra={"telegram_id": tg})
            try:
                group_resp = await client.post(
                    f"{settings.BOT_NOTIFY_URL}/notify/send_group",
                    json={"text": tg_text},
                    headers=_notify_headers(),
                )
                # Group delivery is a fallback channel. Keep task successful even if this path is not configured.
                if group_resp.is_error:
                    log.warning(
                        "contact_feedback_group_send_failed",
                        extra={"status_code": group_resp.status_code, "body": group_resp.text[:500]},
                    )
            except Exception:
                log.warning("contact_feedback_group_send_exception")

    try:
        asyncio.run(_send())
    except Exception:
        log.exception("contact_feedback_tg_send_failed", extra={"recipients": telegram_ids})
        raise
    log.info("contact_feedback_tg_sent", extra={"recipients": telegram_ids})
def _notify_headers() -> dict[str, str]:
    return {"X-Internal-Token": str(getattr(settings, "INTERNAL_TOKEN", ""))}
