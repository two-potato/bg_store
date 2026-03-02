import os
import hmac
import hashlib
import time
import aiohttp
from fastapi import FastAPI, Response
import logging
from pydantic import BaseModel
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from prometheus_client import Counter, Summary, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
log = logging.getLogger("bot")

BACKEND_URL = os.getenv("BACKEND_URL","http://backend:8000")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN","change-me")
ORDER_APPROVE_SECRET = os.getenv("ORDER_APPROVE_SECRET","dev-secret")
MANAGERS_GROUP_ID = int(os.getenv("MANAGERS_GROUP_ID", "0"))  # Telegram chat id of managers group (negative for supergroups)
TWA_WEBAPP_URL = os.getenv("TWA_WEBAPP_URL", "https://example.com/webapp/")

# Prometheus metrics
NOTIFY_SENT = Counter("bot_notify_sent_total", "Notifications sent", ["type"])  # type: kb, document
CALLBACKS = Counter("bot_callbacks_total", "Callback queries processed", ["action"])  # action: approve/reject/other
REQUEST_TIME = Summary("bot_request_latency_seconds", "Time spent processing request")

class MsgKb(BaseModel):
    telegram_id: int
    text: str
    keyboard: list[list[dict]]

@app.post("/notify/send_kb")
async def send_kb(m: MsgKb):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(**btn) for btn in row] for row in m.keyboard])
    await bot.send_message(m.telegram_id, m.text, reply_markup=kb, parse_mode="HTML")
    try:
        log.info("notify_send_kb", extra={"telegram_id": m.telegram_id, "len": len(m.text or ""), "rows": len(m.keyboard)})
    except Exception:
        pass
    NOTIFY_SENT.labels(type="kb").inc()
    return {"ok": True}

class DocMsg(BaseModel):
    telegram_id: int
    caption: str | None = None
    path: str

@app.post("/notify/send_document")
async def send_document(m: DocMsg):
    await bot.send_document(m.telegram_id, FSInputFile(m.path), caption=m.caption)
    try:
        log.info("notify_send_document", extra={"telegram_id": m.telegram_id, "path": m.path})
    except Exception:
        pass
    NOTIFY_SENT.labels(type="document").inc()
    return {"ok": True}

@dp.message(Command("start"))
async def start(m: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Открыть магазин", web_app=WebAppInfo(url=TWA_WEBAPP_URL))]],
        resize_keyboard=True
    )
    await m.answer("Добро пожаловать в магазин!", reply_markup=kb)
    try:
        log.info("bot_start_cmd", extra={"user_id": m.from_user.id if m.from_user else None})
    except Exception:
        pass

def verify_sig(order_id:int, admin_tg_id:int, ts:int, sig:str, skew:int=900)->bool:
    # Reject too old callbacks
    now = int(time.time())
    if abs(now - ts) > skew:
        return False
    msg = f"{order_id}:{admin_tg_id}:{ts}".encode()
    good = hmac.new(ORDER_APPROVE_SECRET.encode(), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(good, sig)

@dp.callback_query()
async def on_callback(cb: types.CallbackQuery):
    data = cb.data or ""
    if not (data.startswith("approve:") or data.startswith("reject:")):
        CALLBACKS.labels(action="other").inc()
        try:
            log.info("callback_other", extra={"from": cb.from_user.id if cb.from_user else None, "data": data[:100]})
        except Exception:
            pass
        return
    try:
        # New format: action:order_id:ts:sig
        parts = data.split(":", 3)
        if len(parts) == 4:
            action, order_id, ts, sig = parts
            order_id = int(order_id)
            ts = int(ts)
        else:
            # Backward-compatible fallback (no ts)
            action, order_id, sig = data.split(":", 2)
            order_id = int(order_id)
            ts = int(time.time())
    except Exception:
        await cb.answer("Некорректные данные", show_alert=True)
        CALLBACKS.labels(action="bad").inc()
        try:
            log.info("callback_bad", extra={"from": cb.from_user.id if cb.from_user else None, "data": data[:100]})
        except Exception:
            pass
        return
    admin_tg = cb.from_user.id
    if not verify_sig(order_id, admin_tg, ts, sig):
        await cb.answer("Подпись недействительна.", show_alert=True)
        CALLBACKS.labels(action="invalid").inc()
        try:
            log.info("callback_invalid_sig", extra={"from": admin_tg, "order_id": order_id, "ts": ts})
        except Exception:
            pass
        return
    url = f"{BACKEND_URL}/api/orders/{order_id}/{ 'approve' if action=='approve' else 'reject' }/"
    async with aiohttp.ClientSession() as s:
        r = await s.post(url, headers={"X-Internal-Token": INTERNAL_TOKEN, "X-Admin-Telegram-Id": str(admin_tg)})
        if r.status == 200:
            await cb.message.edit_text(f"Заказ #{order_id}: {'подтверждён ✅' if action=='approve' else 'отклонён ❌'}")
            await cb.answer("Готово")
            try:
                log.info("callback_processed", extra={"action": action, "order_id": order_id, "admin_tg": admin_tg})
            except Exception:
                pass
        else:
            await cb.answer(f"Ошибка: {r.status}", show_alert=True)
            try:
                log.info("callback_backend_error", extra={"status": r.status, "action": action, "order_id": order_id, "admin_tg": admin_tg})
            except Exception:
                pass
    CALLBACKS.labels(action="approve" if action=="approve" else "reject").inc()

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

class GroupMsg(BaseModel):
    text: str

@app.post("/notify/send_group")
async def send_group(m: GroupMsg):
    if not MANAGERS_GROUP_ID:
        return {"ok": False, "error": "MANAGERS_GROUP_ID not set"}
    await bot.send_message(chat_id=MANAGERS_GROUP_ID, text=m.text, parse_mode="HTML")
    NOTIFY_SENT.labels(type="kb").inc()
    return {"ok": True}

@app.on_event("startup")
async def _startup():
    import asyncio
    asyncio.create_task(dp.start_polling(bot))
