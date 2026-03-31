from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, HTTPException, Query


def _base_url() -> str:
    return str(os.getenv("BACKEND_BASE_URL", "http://backend:8000")).strip().rstrip("/")


def _timeout() -> float:
    return float(os.getenv("BACKEND_TIMEOUT_SECONDS", "2.0"))


def _ready_timeout() -> float:
    return float(os.getenv("BACKEND_READY_TIMEOUT_SECONDS", "3.0"))


def _service_port() -> int:
    return int(os.getenv("SERVICE_PORT", "8010"))


def _internal_token() -> str:
    return str(os.getenv("BACKEND_INTERNAL_TOKEN", "change-me")).strip()


SERVICE_NAME = os.getenv("SERVICE_NAME", "search-api")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.2.0")
PLATFORM_UPSTREAM_MODE = os.getenv("PLATFORM_UPSTREAM_MODE", "django-inline")
PLATFORM_SHADOW_ENABLED = os.getenv("PLATFORM_SHADOW_ENABLED", "0")
PLATFORM_SHADOW_SURFACES = os.getenv("PLATFORM_SHADOW_SURFACES", "")
PLATFORM_CANARY_ENABLED = os.getenv("PLATFORM_CANARY_ENABLED", "0")
PLATFORM_CANARY_SURFACES = os.getenv("PLATFORM_CANARY_SURFACES", "")
PLATFORM_CANARY_PERCENT = os.getenv("PLATFORM_CANARY_PERCENT", "0")
PLATFORM_ROLLOUT_LABEL = os.getenv("PLATFORM_ROLLOUT_LABEL", "search-service")
PLATFORM_OBSERVABILITY_LABEL = os.getenv("PLATFORM_OBSERVABILITY_LABEL", "search-service")

app = FastAPI(
    title="Servio search-api",
    version=SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


def _proxy(path: str, *, params: dict[str, object], timeout: float | None = None) -> dict:
    headers = {"X-Internal-Token": _internal_token()}
    with httpx.Client(timeout=timeout or _timeout()) as client:
        response = client.get(f"{_base_url()}{path}", params=params, headers=headers)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict) or not payload.get("ok"):
        raise HTTPException(status_code=503, detail="backend inline search payload malformed")
    payload["service_source"] = "search-api"
    return payload


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "service": SERVICE_NAME,
        "port": _service_port(),
        "backend_base_url": _base_url(),
        "rollout": {
            "mode": PLATFORM_UPSTREAM_MODE,
            "shadow_enabled": PLATFORM_SHADOW_ENABLED == "1",
            "shadow_surfaces": [item for item in PLATFORM_SHADOW_SURFACES.split(",") if item],
            "canary_enabled": PLATFORM_CANARY_ENABLED == "1",
            "canary_surfaces": [item for item in PLATFORM_CANARY_SURFACES.split(",") if item],
            "canary_percent": int(PLATFORM_CANARY_PERCENT or "0"),
            "label": PLATFORM_ROLLOUT_LABEL,
            "observability_label": PLATFORM_OBSERVABILITY_LABEL,
        },
    }


@app.get("/ready")
def ready() -> dict[str, object]:
    try:
        _proxy(
            "/api/internal/search/suggestions/",
            params={"q": "ready", "limit": 1, "country_limit": 0, "user_id": 0},
            timeout=_ready_timeout(),
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"backend internal search unavailable: {exc}") from exc
    return {"ok": True, "service": SERVICE_NAME}


@app.get("/v1/search/query")
def search_query(
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=24, ge=1, le=64),
    country_limit: int = Query(default=6, ge=0, le=24),
    request_id: str = Query(default="", max_length=128),
    user_id: int = Query(default=0, ge=0),
) -> dict[str, object]:
    params = {
        "q": q,
        "limit": limit,
        "country_limit": country_limit,
        "request_id": request_id,
        "user_id": user_id,
    }
    return _proxy("/api/internal/search/query/", params=params)


@app.get("/v1/search/suggestions")
def search_suggestions(
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=10, ge=1, le=32),
    country_limit: int = Query(default=6, ge=0, le=24),
    request_id: str = Query(default="", max_length=128),
    user_id: int = Query(default=0, ge=0),
) -> dict[str, object]:
    params = {
        "q": q,
        "limit": limit,
        "country_limit": country_limit,
        "request_id": request_id,
        "user_id": user_id,
    }
    return _proxy("/api/internal/search/suggestions/", params=params)
