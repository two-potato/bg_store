import os
import time
from pathlib import Path

import aiohttp
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from .common import (
    CALLBACKS,
    NOTIFY_SENT,
    DocMsg,
    GroupMsg,
    MsgKb,
    TextMsg,
    build_runtime,
    env_int,
    require_internal_token,
    register_common_http,
    register_polling_lifecycle,
    verify_sig,
)
from .sentry_runtime import init_sentry

init_sentry("bot-notify")
app = FastAPI()
bot, dp, log = build_runtime()

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "change-me")
ORDER_APPROVE_SECRET = os.getenv("ORDER_APPROVE_SECRET", "dev-secret")
MANAGERS_GROUP_ID = env_int("MANAGERS_GROUP_ID", 0)
NOTIFY_USE_UPDATES_FALLBACK = os.getenv("NOTIFY_USE_UPDATES_FALLBACK", "0") == "1"
ALLOWED_DOC_ROOTS = [
    Path(p).resolve()
    for p in (os.getenv("ALLOWED_DOC_ROOTS", "/app/media,/tmp").split(","))
    if p.strip()
]


class AlertmanagerAlert(BaseModel):
    status: str
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: str | None = None
    endsAt: str | None = None


class AlertmanagerPayload(BaseModel):
    status: str
    alerts: list[AlertmanagerAlert]
    commonLabels: dict[str, str] = Field(default_factory=dict)
    commonAnnotations: dict[str, str] = Field(default_factory=dict)
    externalURL: str | None = None
    groupKey: str | None = None
    version: str | None = None
    receiver: str | None = None
    truncatedAlerts: int | None = None


def _fmt_alert(a: AlertmanagerAlert) -> str:
    sev = (a.labels.get("severity") or "unknown").upper()
    name = a.labels.get("alertname") or "Alert"
    source = a.labels.get("job") or a.labels.get("instance") or "n/a"
    summary = a.annotations.get("summary") or ""
    descr = a.annotations.get("description") or ""
    container = a.labels.get("container") or a.labels.get("name") or ""

    parts = [f"• <b>{name}</b> [{sev}]"]
    if source:
        parts.append(f"  source: <code>{source}</code>")
    if container:
        parts.append(f"  container: <code>{container}</code>")
    if summary:
        parts.append(f"  {summary}")
    if descr:
        parts.append(f"  {descr}")
    return "\n".join(parts)


async def _send_to_managers_chat(text: str) -> int | None:
    candidates: list[int] = []
    if MANAGERS_GROUP_ID:
        candidates.append(MANAGERS_GROUP_ID)

    # Optional fallback: last active chat from bot updates (private/group/channel).
    # Disabled by default to avoid getUpdates conflicts in multi-instance setups.
    if NOTIFY_USE_UPDATES_FALLBACK:
        try:
            updates = await bot.get_updates(limit=30, timeout=0)
        except Exception:
            updates = []
        for upd in updates:
            chat_id = None
            if upd.message and upd.message.chat:
                chat_id = upd.message.chat.id
            elif upd.channel_post and upd.channel_post.chat:
                chat_id = upd.channel_post.chat.id
            elif upd.callback_query and upd.callback_query.message and upd.callback_query.message.chat:
                chat_id = upd.callback_query.message.chat.id
            if chat_id and chat_id not in candidates:
                candidates.append(chat_id)

    for chat_id in candidates:
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            return chat_id
        except Exception:
            continue
    return None


@app.post("/notify/send_kb")
async def send_kb(payload: MsgKb, _auth: None = Depends(require_internal_token)):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(**btn) for btn in row] for row in payload.keyboard]
    )
    try:
        await bot.send_message(payload.telegram_id, payload.text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest as exc:
        log.warning(
            "notify_send_kb_bad_request telegram_id=%s rows=%s detail=%s",
            payload.telegram_id,
            len(payload.keyboard),
            str(exc),
            extra={"telegram_id": payload.telegram_id, "detail": str(exc), "rows": len(payload.keyboard)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    try:
        log.info(
            "notify_send_kb",
            extra={"telegram_id": payload.telegram_id, "len": len(payload.text or ""), "rows": len(payload.keyboard)},
        )
    except Exception:
        pass
    NOTIFY_SENT.labels(type="kb").inc()
    return {"ok": True}


@app.post("/notify/send_document")
async def send_document(payload: DocMsg, _auth: None = Depends(require_internal_token)):
    requested = Path(payload.path).resolve()
    allowed = any(requested.is_relative_to(root) for root in ALLOWED_DOC_ROOTS)
    if not allowed or not requested.is_file():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document path")
    try:
        await bot.send_document(payload.telegram_id, FSInputFile(str(requested)), caption=payload.caption)
    except TelegramBadRequest as exc:
        log.warning(
            "notify_send_document_bad_request telegram_id=%s path=%s detail=%s",
            payload.telegram_id,
            payload.path,
            str(exc),
            extra={"telegram_id": payload.telegram_id, "path": payload.path, "detail": str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    try:
        log.info("notify_send_document", extra={"telegram_id": payload.telegram_id, "path": payload.path})
    except Exception:
        pass
    NOTIFY_SENT.labels(type="document").inc()
    return {"ok": True}


@app.post("/notify/send_text")
async def send_text(payload: TextMsg, _auth: None = Depends(require_internal_token)):
    try:
        await bot.send_message(payload.telegram_id, payload.text, parse_mode="HTML")
    except TelegramBadRequest as exc:
        log.warning(
            "notify_send_text_bad_request telegram_id=%s len=%s detail=%s",
            payload.telegram_id,
            len(payload.text or ""),
            str(exc),
            extra={"telegram_id": payload.telegram_id, "detail": str(exc), "len": len(payload.text or "")},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    try:
        log.info("notify_send_text", extra={"telegram_id": payload.telegram_id, "len": len(payload.text or "")})
    except Exception:
        pass
    NOTIFY_SENT.labels(type="text").inc()
    return {"ok": True}


@app.post("/notify/send_group")
async def send_group(payload: GroupMsg, _auth: None = Depends(require_internal_token)):
    sent_chat = await _send_to_managers_chat(payload.text)
    if sent_chat is None:
        return {"ok": False, "error": "No reachable chat for notifications"}
    NOTIFY_SENT.labels(type="group").inc()
    return {"ok": True, "chat_id": sent_chat}


@app.post("/notify/alertmanager")
async def alertmanager_webhook(payload: AlertmanagerPayload):
    status_icon = "🚨" if payload.status == "firing" else "✅"
    title = "ALERT FIRING" if payload.status == "firing" else "ALERT RESOLVED"
    lines = [f"{status_icon} <b>{title}</b>"]

    alerts = payload.alerts[:8]
    for alert in alerts:
        lines.append(_fmt_alert(alert))
    if len(payload.alerts) > len(alerts):
        lines.append(f"… and {len(payload.alerts) - len(alerts)} more alerts")

    sent_chat = await _send_to_managers_chat("\n\n".join(lines))
    if sent_chat is None:
        log.error(
            "alertmanager_delivery_failed",
            extra={"alerts_total": len(payload.alerts), "managers_group_id": MANAGERS_GROUP_ID},
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No reachable chat for alerts")
    NOTIFY_SENT.labels(type="group").inc()
    return {"ok": True, "sent": len(alerts), "total": len(payload.alerts), "chat_id": sent_chat}


@dp.message(Command("start"))
async def start(message):
    await message.answer(
        "Это бот уведомлений BG Shop.\n"
        "Сюда приходят уведомления о заказах и изменении их статусов."
    )
    try:
        log.info("bot_start_cmd", extra={"user_id": message.from_user.id if message.from_user else None})
    except Exception:
        pass


@dp.callback_query()
async def on_callback(callback):
    data = callback.data or ""
    if not (data.startswith("approve:") or data.startswith("reject:")):
        CALLBACKS.labels(action="other").inc()
        return
    try:
        parts = data.split(":", 3)
        if len(parts) == 4:
            action, order_id, ts, sig = parts
            order_id = int(order_id)
            ts = int(ts)
        else:
            action, order_id, sig = data.split(":", 2)
            order_id = int(order_id)
            ts = int(time.time())
    except Exception:
        await callback.answer("Некорректные данные", show_alert=True)
        CALLBACKS.labels(action="bad").inc()
        return

    admin_tg = callback.from_user.id
    if not verify_sig(order_id, admin_tg, ts, sig, ORDER_APPROVE_SECRET):
        await callback.answer("Подпись недействительна.", show_alert=True)
        CALLBACKS.labels(action="invalid").inc()
        return

    url = f"{BACKEND_URL}/api/orders/{order_id}/{'approve' if action == 'approve' else 'reject'}/"
    async with aiohttp.ClientSession() as session:
        resp = await session.post(
            url,
            headers={"X-Internal-Token": INTERNAL_TOKEN, "X-Admin-Telegram-Id": str(admin_tg)},
        )
        if resp.status == 200:
            await callback.message.edit_text(
                f"Заказ #{order_id}: {'подтверждён ✅' if action == 'approve' else 'отклонён ❌'}"
            )
            await callback.answer("Готово")
        else:
            await callback.answer(f"Ошибка: {resp.status}", show_alert=True)

    CALLBACKS.labels(action="approve" if action == "approve" else "reject").inc()


register_common_http(app)
register_polling_lifecycle(app, bot=bot, dp=dp, log=log, disable_by_default="1")
