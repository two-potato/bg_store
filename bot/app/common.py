import hashlib
import hmac
import logging
import os
import time

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from fastapi import FastAPI, Header, HTTPException, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Summary, generate_latest
from pydantic import BaseModel


# Prometheus metrics
NOTIFY_SENT = Counter("bot_notify_sent_total", "Notifications sent", ["type"])
CALLBACKS = Counter("bot_callbacks_total", "Callback queries processed", ["action"])
REQUEST_TIME = Summary("bot_request_latency_seconds", "Time spent processing request")


def build_runtime() -> tuple[Bot, Dispatcher, logging.Logger]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    bot_timeout = env_int("BOT_HTTP_TIMEOUT", 60)
    bot_conn_limit = env_int("BOT_HTTP_CONNECTOR_LIMIT", 200)
    session = AiohttpSession(timeout=bot_timeout, limit=bot_conn_limit)
    bot = Bot(token=token, session=session)
    dp = Dispatcher()
    log = logging.getLogger("bot")
    return bot, dp, log


def env_int(name: str, default: int = 0) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except Exception:
        return default


def verify_sig(order_id: int, admin_tg_id: int, ts: int, sig: str, secret: str, skew: int = 900) -> bool:
    now = int(time.time())
    if abs(now - ts) > skew:
        return False
    msg = f"{order_id}:{admin_tg_id}:{ts}".encode()
    good = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(good, sig)


def require_internal_token(x_internal_token: str | None = Header(default=None, alias="X-Internal-Token")) -> None:
    expected = (os.getenv("INTERNAL_TOKEN") or "").strip()
    provided = (x_internal_token or "").strip()
    if not expected:
        return
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def register_common_http(app: FastAPI) -> None:
    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


class MsgKb(BaseModel):
    telegram_id: int
    text: str
    keyboard: list[list[dict]]


class DocMsg(BaseModel):
    telegram_id: int
    caption: str | None = None
    path: str


class TextMsg(BaseModel):
    telegram_id: int
    text: str


class GroupMsg(BaseModel):
    text: str
