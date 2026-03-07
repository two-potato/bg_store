import logging
from typing import Iterable

import httpx
from django.conf import settings
from django.core.mail import send_mail

from users.models import UserProfile

log = logging.getLogger("core.notifications")


def notify_headers() -> dict[str, str]:
    return {"X-Internal-Token": str(getattr(settings, "INTERNAL_TOKEN", ""))}


def admin_emails() -> list[str]:
    emails = list(getattr(settings, "ADMIN_NOTIFY_EMAILS", []) or [])
    if emails:
        return sorted({e.strip() for e in emails if e and e.strip()})
    admins = getattr(settings, "ADMINS", []) or []
    return sorted({email for _, email in admins if email})


def admin_telegram_ids() -> list[int]:
    recipients: set[int] = set()
    explicit = list(getattr(settings, "ADMIN_NOTIFY_TELEGRAM_IDS", []) or [])
    recipients.update(int(v) for v in explicit if str(v).strip().lstrip("-").isdigit())
    qs = UserProfile.objects.filter(
        role__in=[UserProfile.Role.ADMIN, UserProfile.Role.MANAGER],
        telegram_id__isnull=False,
    ).values_list("telegram_id", flat=True)
    recipients.update(int(v) for v in qs if v)
    return sorted(recipients)


def send_email_notification(subject: str, message: str, recipients: Iterable[str] | None = None) -> bool:
    to = list(recipients or admin_emails())
    if not to:
        log.warning("notify_email_no_recipients", extra={"subject": subject})
        return False
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=to,
            fail_silently=False,
        )
        log.info("notify_email_sent", extra={"subject": subject, "recipients": to})
        return True
    except Exception:
        log.exception("notify_email_send_failed", extra={"subject": subject, "recipients": to})
        return False


def send_telegram_text(telegram_id: int, text: str, timeout: float = 10.0) -> bool:
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{settings.BOT_NOTIFY_URL}/notify/send_text",
                json={"telegram_id": int(telegram_id), "text": text},
                headers=notify_headers(),
            )
        if resp.is_error:
            log.warning(
                "notify_tg_send_failed",
                extra={"telegram_id": telegram_id, "status_code": resp.status_code, "body": resp.text[:500]},
            )
            return False
        return True
    except Exception:
        log.exception("notify_tg_send_exception", extra={"telegram_id": telegram_id})
        return False


def send_telegram_bulk(text: str, recipients: Iterable[int] | None = None) -> int:
    ids = [int(v) for v in (recipients or admin_telegram_ids()) if v]
    sent = 0
    for tg in ids:
        if send_telegram_text(tg, text):
            sent += 1
    if ids and sent == 0:
        log.warning("notify_tg_bulk_all_failed", extra={"recipients": ids})
    return sent


def send_telegram_group(text: str, timeout: float = 10.0) -> bool:
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{settings.BOT_NOTIFY_URL}/notify/send_group",
                json={"text": text},
                headers=notify_headers(),
            )
        if resp.is_error:
            log.warning("notify_group_failed", extra={"status_code": resp.status_code, "body": resp.text[:500]})
            return False
        return bool(resp.json().get("ok"))
    except Exception:
        log.exception("notify_group_exception")
        return False
