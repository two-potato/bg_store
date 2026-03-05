import os
import time
from pathlib import Path

import aiohttp
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from fastapi import Depends, FastAPI, HTTPException, status

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
    verify_sig,
)

app = FastAPI()
bot, dp, log = build_runtime()

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "change-me")
ORDER_APPROVE_SECRET = os.getenv("ORDER_APPROVE_SECRET", "dev-secret")
MANAGERS_GROUP_ID = env_int("MANAGERS_GROUP_ID", 0)
ALLOWED_DOC_ROOTS = [
    Path(p).resolve()
    for p in (os.getenv("ALLOWED_DOC_ROOTS", "/app/media,/tmp").split(","))
    if p.strip()
]


@app.post("/notify/send_kb")
async def send_kb(payload: MsgKb, _auth: None = Depends(require_internal_token)):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(**btn) for btn in row] for row in payload.keyboard]
    )
    await bot.send_message(payload.telegram_id, payload.text, reply_markup=kb, parse_mode="HTML")
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
    await bot.send_document(payload.telegram_id, FSInputFile(str(requested)), caption=payload.caption)
    try:
        log.info("notify_send_document", extra={"telegram_id": payload.telegram_id, "path": payload.path})
    except Exception:
        pass
    NOTIFY_SENT.labels(type="document").inc()
    return {"ok": True}


@app.post("/notify/send_text")
async def send_text(payload: TextMsg, _auth: None = Depends(require_internal_token)):
    await bot.send_message(payload.telegram_id, payload.text, parse_mode="HTML")
    try:
        log.info("notify_send_text", extra={"telegram_id": payload.telegram_id, "len": len(payload.text or "")})
    except Exception:
        pass
    NOTIFY_SENT.labels(type="text").inc()
    return {"ok": True}


@app.post("/notify/send_group")
async def send_group(payload: GroupMsg, _auth: None = Depends(require_internal_token)):
    if not MANAGERS_GROUP_ID:
        return {"ok": False, "error": "MANAGERS_GROUP_ID not set"}
    await bot.send_message(chat_id=MANAGERS_GROUP_ID, text=payload.text, parse_mode="HTML")
    NOTIFY_SENT.labels(type="group").inc()
    return {"ok": True}


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


@app.on_event("startup")
async def startup_event():
    import asyncio

    if os.getenv("BOT_DISABLE_POLLING", "0") == "1":
        try:
            log.info("bot_polling_disabled")
        except Exception:
            pass
        return

    try:
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception:
        pass
    polling_timeout = env_int("BOT_POLLING_TIMEOUT", 30)
    asyncio.create_task(
        dp.start_polling(
            bot,
            polling_timeout=polling_timeout,
            allowed_updates=dp.resolve_used_update_types(),
            handle_signals=False,
        )
    )
