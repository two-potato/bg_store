import os
import hmac
import hashlib
import aiohttp
from fastapi import FastAPI, Response
from pydantic import BaseModel
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from prometheus_client import Counter, Summary, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI()
bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
dp = Dispatcher()

BACKEND_URL = os.getenv("BACKEND_URL","http://backend:8000")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN","change-me")
ORDER_APPROVE_SECRET = os.getenv("ORDER_APPROVE_SECRET","dev-secret")

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
    NOTIFY_SENT.labels(type="kb").inc()
    return {"ok": True}

class DocMsg(BaseModel):
    telegram_id: int
    caption: str | None = None
    path: str

@app.post("/notify/send_document")
async def send_document(m: DocMsg):
    await bot.send_document(m.telegram_id, FSInputFile(m.path), caption=m.caption)
    NOTIFY_SENT.labels(type="document").inc()
    return {"ok": True}

@dp.message(Command("start"))
async def start(m: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Открыть магазин", web_app=WebAppInfo(url="https://example.com/webapp/"))]],
        resize_keyboard=True
    )
    await m.answer("Добро пожаловать в магазин!", reply_markup=kb)

def verify_sig(order_id:int, admin_tg_id:int, sig:str)->bool:
    msg = f"{order_id}:{admin_tg_id}".encode()
    good = hmac.new(ORDER_APPROVE_SECRET.encode(), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(good, sig)

@dp.callback_query()
async def on_callback(cb: types.CallbackQuery):
    data = cb.data or ""
    if not (data.startswith("approve:") or data.startswith("reject:")):
        CALLBACKS.labels(action="other").inc()
        return
    try:
        action, order_id, sig = data.split(":", 2)
        order_id = int(order_id)
    except Exception:
        await cb.answer("Некорректные данные", show_alert=True)
        CALLBACKS.labels(action="bad").inc()
        return
    admin_tg = cb.from_user.id
    if not verify_sig(order_id, admin_tg, sig):
        await cb.answer("Подпись недействительна.", show_alert=True)
        CALLBACKS.labels(action="invalid").inc()
        return
    url = f"{BACKEND_URL}/api/orders/{order_id}/{ 'approve' if action=='approve' else 'reject' }/"
    async with aiohttp.ClientSession() as s:
        r = await s.post(url, headers={"X-Internal-Token": INTERNAL_TOKEN, "X-Admin-Telegram-Id": str(admin_tg)})
        if r.status == 200:
            await cb.message.edit_text(f"Заказ #{order_id}: {'подтверждён ✅' if action=='approve' else 'отклонён ❌'}")
            await cb.answer("Готово")
        else:
            await cb.answer(f"Ошибка: {r.status}", show_alert=True)
    CALLBACKS.labels(action="approve" if action=="approve" else "reject").inc()

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.on_event("startup")
async def _startup():
    import asyncio
    asyncio.create_task(dp.start_polling(bot))
