import os

from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from fastapi import FastAPI

from .common import build_runtime, env_int, register_common_http

app = FastAPI()
bot, dp, log = build_runtime()

TWA_WEBAPP_URL = os.getenv("TWA_WEBAPP_URL", "https://example.com/webapp/")


@dp.message(Command("start"))
async def start(message):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Открыть магазин", web_app=WebAppInfo(url=TWA_WEBAPP_URL))]],
        resize_keyboard=True,
    )
    await message.answer("Добро пожаловать в магазин!", reply_markup=kb)
    try:
        log.info("bot_start_cmd", extra={"user_id": message.from_user.id if message.from_user else None})
    except Exception:
        pass


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
