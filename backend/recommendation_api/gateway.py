from __future__ import annotations

import logging
import time
from uuid import uuid4

import httpx
from django.conf import settings

from catalog.api_contracts import normalize_product_card

log = logging.getLogger("recommendation_api")


def _service_url() -> str:
    return str(getattr(settings, "RECOMMENDATION_SERVICE_URL", "http://recommendation-api:8011")).strip().rstrip("/")


def _timeout() -> float:
    return float(getattr(settings, "RECOMMENDATION_SERVICE_TIMEOUT_SECONDS", 0.8))


def _request_id(request) -> str:
    return str(request.headers.get("X-Request-ID") or request.META.get("REQUEST_ID") or "").strip()


def _user_id(request) -> int:
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return 0
    return int(getattr(user, "id", 0) or 0)


def _params(request, *, limit: int) -> dict[str, object]:
    return {"limit": limit, "request_id": _request_id(request), "user_id": _user_id(request)}


def _normalize(payload: dict[str, object], *, latency_ms: int) -> dict[str, object]:
    sections: list[dict[str, object]] = []
    has_products = False
    for raw in payload.get("sections") or []:
        if not isinstance(raw, dict):
            continue
        products = [normalize_product_card(item) for item in raw.get("products") or [] if isinstance(item, dict)]
        has_products = has_products or bool(products)
        sections.append(
            {
                "key": str(raw.get("key") or ""),
                "title": str(raw.get("title") or ""),
                "source": str(raw.get("source") or ""),
                "strategy": str(raw.get("strategy") or ""),
                "tracking_payload": str(raw.get("tracking_payload") or ""),
                "impression_id": str(raw.get("impression_id") or uuid4().hex),
                "fallback_source": str(raw.get("fallback_source") or ""),
                "empty_reason": str(raw.get("empty_reason") or ("" if products else "no_products")),
                "products": products,
            }
        )
    return {
        "ok": bool(payload.get("ok", True)),
        "surface": str(payload.get("surface") or ""),
        "variant": str(payload.get("variant") or "control"),
        "recommendation_id": str(payload.get("recommendation_id") or uuid4().hex),
        "fallback_source": str(payload.get("fallback_source") or ""),
        "empty_reason": str(payload.get("empty_reason") or ("" if has_products else "all_sections_empty")),
        "latency_ms": int(payload.get("latency_ms") or latency_ms),
        "service_source": "recommendation-api",
        "engine_source": str(payload.get("engine_source") or payload.get("source") or "recommendation-api"),
        "sections": sections,
    }


def _degraded(*, surface: str, exc: Exception) -> dict[str, object]:
    log.warning("recommendation_service_degraded", extra={"surface": surface, "reason": str(exc)})
    return {
        "ok": True,
        "surface": surface,
        "variant": "control",
        "recommendation_id": uuid4().hex,
        "fallback_source": "",
        "empty_reason": "service_unavailable",
        "latency_ms": 0,
        "service_source": "recommendation-api",
        "engine_source": "degraded",
        "service_error": type(exc).__name__,
        "sections": [],
    }


def call(path: str, *, request, surface: str, limit: int, method: str = "GET", extra_params: dict[str, object] | None = None, body: dict[str, object] | None = None) -> dict[str, object]:
    started = time.perf_counter()
    params = _params(request, limit=limit)
    params.update(extra_params or {})
    json_body = dict(body or {})
    if method != "GET":
        json_body.update(params)
        params = {}
    try:
        with httpx.Client(timeout=_timeout()) as client:
            response = client.request(method, f"{_service_url()}{path}", params=params or None, json=json_body or None)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("recommendation service returned malformed payload")
        return _normalize(payload, latency_ms=max(0, int((time.perf_counter() - started) * 1000)))
    except Exception as exc:
        return _degraded(surface=surface, exc=exc)
