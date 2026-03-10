import os

from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from fastapi import FastAPI

from .common import build_runtime, register_common_http, register_polling_lifecycle
from .sentry_runtime import init_sentry

init_sentry("bot-shop")
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
register_polling_lifecycle(app, bot=bot, dp=dp, log=log, disable_by_default="0")
