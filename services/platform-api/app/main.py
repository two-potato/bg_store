from __future__ import annotations

import os

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse


def _clean_base_url(value: str | None, fallback: str) -> str:
    candidate = (value or fallback).strip()
    return candidate.rstrip("/")


SERVICE_NAME = os.getenv("SERVICE_NAME", "platform-api")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8010"))
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.0")
BACKEND_BASE_URL = _clean_base_url(os.getenv("BACKEND_BASE_URL"), "http://backend:8000")
BACKEND_HEALTH_URL = os.getenv("BACKEND_HEALTH_URL", f"{BACKEND_BASE_URL}/health/").strip()
PLATFORM_SERVICE_LOG_LEVEL = os.getenv("PLATFORM_SERVICE_LOG_LEVEL", "INFO")
ENABLE_BACKEND_READY_CHECK = os.getenv("ENABLE_BACKEND_READY_CHECK", "1") == "1"

app = FastAPI(
    title=f"Servio {SERVICE_NAME}",
    version=SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "ok": True,
        "service": SERVICE_NAME,
        "port": SERVICE_PORT,
        "log_level": PLATFORM_SERVICE_LOG_LEVEL,
        "backend_base_url": BACKEND_BASE_URL,
        "backend_ready_check": ENABLE_BACKEND_READY_CHECK,
    }


@app.get("/ready")
async def ready():
    if not ENABLE_BACKEND_READY_CHECK:
        return {
            "ok": True,
            "service": SERVICE_NAME,
            "backend": {
                "checked": False,
                "url": BACKEND_HEALTH_URL,
            },
        }

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(BACKEND_HEALTH_URL)
    except httpx.HTTPError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "service": SERVICE_NAME,
                "backend": {
                    "checked": True,
                    "url": BACKEND_HEALTH_URL,
                    "reachable": False,
                    "error": str(exc),
                },
            },
        )

    return JSONResponse(
        status_code=200 if response.is_success else 503,
        content={
            "ok": response.is_success,
            "service": SERVICE_NAME,
            "backend": {
                "checked": True,
                "url": BACKEND_HEALTH_URL,
                "reachable": response.is_success,
                "status_code": response.status_code,
            },
        },
    )
