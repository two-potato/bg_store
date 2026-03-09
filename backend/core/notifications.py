import logging
import smtplib
from typing import Iterable

import httpx
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail

from users.models import UserProfile

log = logging.getLogger("core.notifications")


def _is_valid_telegram_id(value: int) -> bool:
    # Telegram chat ids are signed integers; keep a conservative bound
    # to avoid noisy retries on malformed config/user data.
    return -(10**14) <= int(value) <= 10**14 and int(value) != 0


def notify_headers() -> dict[str, str]:
    return {"X-Internal-Token": str(getattr(settings, "INTERNAL_TOKEN", ""))}


def _response_is_error(resp: httpx.Response) -> bool:
    is_error = getattr(resp, "is_error", None)
    if is_error is not None:
        return bool(is_error)
    status_code = int(getattr(resp, "status_code", 200) or 200)
    return status_code >= 400


def _response_excerpt(resp: httpx.Response, limit: int = 500) -> str:
    return (getattr(resp, "text", "") or "")[:limit]


def _telegram_quarantine_key(telegram_id: int) -> str:
    return f"notify:telegram:quarantine:{int(telegram_id)}"


def is_telegram_recipient_quarantined(telegram_id: int) -> bool:
    return bool(cache.get(_telegram_quarantine_key(telegram_id)))


def quarantine_telegram_recipient(telegram_id: int, reason: str, ttl: int | None = None) -> None:
    timeout = ttl or int(getattr(settings, "TELEGRAM_RECIPIENT_QUARANTINE_TTL", 6 * 60 * 60))
    cache.set(_telegram_quarantine_key(telegram_id), reason[:200], timeout=timeout)


def _should_quarantine_telegram_recipient(path: str, resp: httpx.Response, metadata: dict) -> bool:
    if path != "/notify/send_text":
        return False
    telegram_id = metadata.get("telegram_id")
    if telegram_id in {None, ""}:
        return False
    status_code = int(getattr(resp, "status_code", 200) or 200)
    if status_code not in {400, 403}:
        return False
    body = _response_excerpt(resp).lower()
    return "chat not found" in body or "bot was blocked" in body or "user is deactivated" in body


def post_notify_json(
    path: str,
    payload: dict,
    *,
    timeout: float = 10.0,
    logger: logging.Logger | None = None,
    failure_event: str = "notify_http_failed",
    success_event: str | None = None,
    extra: dict | None = None,
) -> tuple[bool, httpx.Response | None]:
    log_target = logger or log
    metadata = {"path": path, **(extra or {})}
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{settings.BOT_NOTIFY_URL}{path}",
                json=payload,
                headers=notify_headers(),
            )
    except Exception:
        log_target.exception(f"{failure_event}_exception", extra=metadata)
        return False, None
    if _response_is_error(resp):
        if _should_quarantine_telegram_recipient(path, resp, metadata):
            quarantine_telegram_recipient(int(metadata["telegram_id"]), _response_excerpt(resp))
        log_target.warning(
            failure_event,
            extra={
                **metadata,
                "status_code": getattr(resp, "status_code", None),
                "body": _response_excerpt(resp),
            },
        )
        return False, resp
    if success_event:
        log_target.info(success_event, extra=metadata)
    return True, resp


async def apost_notify_json(
    client: httpx.AsyncClient,
    path: str,
    payload: dict,
    *,
    logger: logging.Logger | None = None,
    failure_event: str = "notify_http_failed",
    success_event: str | None = None,
    extra: dict | None = None,
) -> tuple[bool, httpx.Response | None]:
    log_target = logger or log
    metadata = {"path": path, **(extra or {})}
    try:
        resp = await client.post(
            f"{settings.BOT_NOTIFY_URL}{path}",
            json=payload,
            headers=notify_headers(),
        )
    except Exception:
        log_target.exception(f"{failure_event}_exception", extra=metadata)
        return False, None
    if _response_is_error(resp):
        if _should_quarantine_telegram_recipient(path, resp, metadata):
            quarantine_telegram_recipient(int(metadata["telegram_id"]), _response_excerpt(resp))
        log_target.warning(
            failure_event,
            extra={
                **metadata,
                "status_code": getattr(resp, "status_code", None),
                "body": _response_excerpt(resp),
            },
        )
        return False, resp
    if success_event:
        log_target.info(success_event, extra=metadata)
    return True, resp


def admin_emails() -> list[str]:
    emails = list(getattr(settings, "ADMIN_NOTIFY_EMAILS", []) or [])
    if emails:
        return sorted({e.strip() for e in emails if e and e.strip()})
    admins = getattr(settings, "ADMINS", []) or []
    return sorted({email for _, email in admins if email})


def admin_telegram_ids() -> list[int]:
    recipients: set[int] = set()
    explicit = list(getattr(settings, "ADMIN_NOTIFY_TELEGRAM_IDS", []) or [])
    recipients.update(
        int(v)
        for v in explicit
        if (
            str(v).strip().lstrip("-").isdigit()
            and _is_valid_telegram_id(int(v))
            and not is_telegram_recipient_quarantined(int(v))
        )
    )
    qs = UserProfile.objects.filter(
        role__in=[UserProfile.Role.ADMIN, UserProfile.Role.MANAGER],
        telegram_id__isnull=False,
    ).values_list("telegram_id", flat=True)
    recipients.update(
        int(v)
        for v in qs
        if v and _is_valid_telegram_id(int(v)) and not is_telegram_recipient_quarantined(int(v))
    )
    return sorted(recipients)


def send_mail_message(
    *,
    subject: str,
    message: str,
    recipient_list: Iterable[str],
    logger: logging.Logger | None = None,
    extra: dict | None = None,
) -> bool:
    to = sorted({email.strip() for email in recipient_list if email and email.strip()})
    log_target = logger or log
    payload = {"subject": subject, "recipients": to, **(extra or {})}
    if not to:
        log_target.warning("notify_email_no_recipients", extra=payload)
        return False
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=to,
            fail_silently=False,
        )
        log_target.info("notify_email_sent", extra=payload)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        # Transport failures are operational issues. Keep them visible without
        # polluting error logs with full tracebacks on every retry.
        log_target.warning("notify_email_transport_failed", extra={**payload, "error": str(exc)})
        return False
    except Exception:
        log_target.exception("notify_email_send_failed", extra=payload)
        return False


def send_email_notification(subject: str, message: str, recipients: Iterable[str] | None = None) -> bool:
    return send_mail_message(subject=subject, message=message, recipient_list=list(recipients or admin_emails()))


def send_telegram_text(telegram_id: int, text: str, timeout: float = 10.0) -> bool:
    if is_telegram_recipient_quarantined(int(telegram_id)):
        log.info("notify_tg_send_skipped_quarantined", extra={"telegram_id": int(telegram_id)})
        return False
    ok, _ = post_notify_json(
        "/notify/send_text",
        {"telegram_id": int(telegram_id), "text": text},
        timeout=timeout,
        logger=log,
        failure_event="notify_tg_send_failed",
        extra={"telegram_id": int(telegram_id)},
    )
    return ok


def send_telegram_bulk(text: str, recipients: Iterable[int] | None = None) -> int:
    ids = [int(v) for v in (recipients or admin_telegram_ids()) if v and _is_valid_telegram_id(int(v))]
    sent = 0
    for tg in ids:
        if send_telegram_text(tg, text):
            sent += 1
    if ids and sent == 0:
        log.warning("notify_tg_bulk_all_failed", extra={"recipients": ids})
    return sent


def send_telegram_group(text: str, timeout: float = 10.0) -> bool:
    ok, resp = post_notify_json(
        "/notify/send_group",
        {"text": text},
        timeout=timeout,
        logger=log,
        failure_event="notify_group_failed",
    )
    if not ok or resp is None:
        return False
    try:
        return bool(resp.json().get("ok"))
    except Exception:
        log.warning("notify_group_invalid_response")
        return False
