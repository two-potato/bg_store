from __future__ import annotations

import os
from decimal import Decimal

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field


def _base_url() -> str:
    return str(os.getenv("BACKEND_API_URL", "http://backend:8000/api")).strip().rstrip("/")


def _timeout() -> float:
    return float(os.getenv("BACKEND_TIMEOUT_SECONDS", "2.0"))


def _service_port() -> int:
    return int(os.getenv("SERVICE_PORT", "8011"))


SERVICE_NAME = os.getenv("SERVICE_NAME", "recommendation-api")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.0")
PLATFORM_UPSTREAM_MODE = os.getenv("PLATFORM_UPSTREAM_MODE", "django-inline")
PLATFORM_SHADOW_ENABLED = os.getenv("PLATFORM_SHADOW_ENABLED", "0")
PLATFORM_SHADOW_SURFACES = os.getenv("PLATFORM_SHADOW_SURFACES", "")
PLATFORM_CANARY_ENABLED = os.getenv("PLATFORM_CANARY_ENABLED", "0")
PLATFORM_CANARY_SURFACES = os.getenv("PLATFORM_CANARY_SURFACES", "")
PLATFORM_CANARY_PERCENT = os.getenv("PLATFORM_CANARY_PERCENT", "0")
PLATFORM_ROLLOUT_LABEL = os.getenv("PLATFORM_ROLLOUT_LABEL", "recommendation-service")
PLATFORM_OBSERVABILITY_LABEL = os.getenv("PLATFORM_OBSERVABILITY_LABEL", "recommendation-service")

app = FastAPI(
    title="Servio recommendation-api",
    version=SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


class RecommendationSeedRequest(BaseModel):
    product_ids: list[int] = Field(default_factory=list, min_length=1, max_length=64)
    limit: int = Field(default=8, ge=1, le=32)
    request_id: str = Field(default="")
    user_id: int = Field(default=0, ge=0)


def _price(value: object) -> str:
    try:
        return f"{Decimal(str(value)):.2f}"
    except Exception:
        return "0.00"


def _card(item: dict) -> dict:
    brand = item.get("brand") if isinstance(item.get("brand"), dict) else {}
    images = item.get("images") if isinstance(item.get("images"), list) else []
    image_url = ""
    if images and isinstance(images[0], dict):
        image_url = str(images[0].get("url") or "")
    return {
        "id": int(item.get("id") or 0),
        "slug": str(item.get("slug") or ""),
        "sku": str(item.get("sku") or ""),
        "name": str(item.get("name") or ""),
        "image_url": image_url,
        "price": _price(item.get("price") or 0),
        "stock_qty": int(item.get("stock_qty") or 0),
        "min_order_qty": int(item.get("min_order_qty") or 1),
        "brand_name": str((brand or {}).get("name") or ""),
        "seller_name": str(item.get("seller") or ""),
        "rating_avg": 0.0,
        "rating_count": 0,
        "is_new": bool(item.get("is_new") or False),
        "is_promo": bool(item.get("is_promo") or False),
    }


def _catalog_products(params: dict[str, object]) -> list[dict]:
    with httpx.Client(timeout=_timeout()) as client:
        response = client.get(f"{_base_url()}/catalog/products/", params=params)
        response.raise_for_status()
        payload = response.json()
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        return [item for item in payload.get("results", []) if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _catalog_product(product_id: int) -> dict | None:
    with httpx.Client(timeout=_timeout()) as client:
        response = client.get(f"{_base_url()}/catalog/products/{product_id}/")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
    return payload if isinstance(payload, dict) else None


def _dedupe(cards: list[dict], *, exclude: set[int] | None = None, limit: int = 8) -> list[dict]:
    exclude = exclude or set()
    seen = set(exclude)
    out: list[dict] = []
    for card in cards:
        product_id = int(card.get("id") or 0)
        if product_id <= 0 or product_id in seen:
            continue
        seen.add(product_id)
        out.append(card)
        if len(out) >= limit:
            break
    return out


def _section(*, key: str, title: str, products: list[dict], source: str, strategy: str) -> dict:
    return {
        "key": key,
        "title": title,
        "source": source,
        "strategy": strategy,
        "tracking_payload": "",
        "products": products,
    }


def _related_cards(seed_product: dict, *, limit: int) -> list[dict]:
    cards: list[dict] = []
    category_id = seed_product.get("category")
    brand = seed_product.get("brand") if isinstance(seed_product.get("brand"), dict) else {}
    brand_id = brand.get("id")
    if category_id:
        cards.extend([_card(item) for item in _catalog_products({"category": category_id, "limit": max(limit * 2, 16)})])
    if brand_id:
        cards.extend([_card(item) for item in _catalog_products({"brand": brand_id, "limit": max(limit * 2, 16)})])
    cards.extend([_card(item) for item in _catalog_products({"is_promo": "true", "limit": max(limit, 8)})])
    return _dedupe(cards, exclude={int(seed_product.get("id") or 0)}, limit=limit)


def _popular_cards(*, limit: int) -> list[dict]:
    rows = _catalog_products({"limit": max(limit * 3, 24)})
    return _dedupe([_card(item) for item in rows], limit=limit)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "service": SERVICE_NAME,
        "port": _service_port(),
        "backend_api_url": _base_url(),
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
        _ = _catalog_products({"limit": 1})
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"backend catalog unavailable: {exc}") from exc
    return {"ok": True, "service": SERVICE_NAME}


@app.get("/v1/recommendations/home")
def recommendations_home(
    limit: int = Query(default=8, ge=1, le=32),
    request_id: str = Query(default="", max_length=128),
    user_id: int = Query(default=0, ge=0),
) -> dict[str, object]:
    popular = _popular_cards(limit=limit)
    promos = _dedupe([_card(item) for item in _catalog_products({"is_promo": "true", "limit": max(limit * 2, 12)})], limit=limit)
    fresh = _dedupe([_card(item) for item in _catalog_products({"is_new": "true", "limit": max(limit * 2, 12)})], limit=limit)
    return {
        "ok": True,
        "surface": "home",
        "variant": "control",
        "sections": [
            _section(key="recommended_for_you", title="Рекомендуем для вас", products=promos or popular, source="home_for_you", strategy="fastapi_bootstrap"),
            _section(key="recently_viewed", title="Вы смотрели", products=fresh[:limit], source="home_recently_viewed", strategy="fastapi_bootstrap"),
            _section(key="watchlist", title="Из ваших подписок", products=promos[:limit], source="home_watchlist", strategy="fastapi_bootstrap"),
            _section(key="popular", title="Популярное", products=popular, source="home_popular", strategy="fastapi_bootstrap"),
            _section(key="replenishment", title="Пора пополнить", products=fresh or popular, source="home_replenishment", strategy="fastapi_bootstrap"),
        ],
        "request_id": request_id,
        "user_id": user_id,
    }


@app.get("/v1/recommendations/product/{product_id}")
def recommendations_product(
    product_id: int,
    limit: int = Query(default=12, ge=1, le=32),
    request_id: str = Query(default="", max_length=128),
    user_id: int = Query(default=0, ge=0),
) -> dict[str, object]:
    seed = _catalog_product(product_id)
    if not seed:
        raise HTTPException(status_code=404, detail="product not found")
    related = _related_cards(seed, limit=limit)
    substitutes = _dedupe(list(reversed(related)), limit=min(8, limit))
    accessories = _dedupe(_popular_cards(limit=max(8, limit // 2)), exclude={product_id}, limit=min(8, limit))
    return {
        "ok": True,
        "surface": "pdp",
        "variant": "control",
        "sections": [
            _section(key="similar_products", title="Похожие товары", products=related, source="product_similar", strategy="fastapi_bootstrap"),
            _section(key="accessory_products", title="С этим товаром берут", products=accessories, source="product_accessories", strategy="fastapi_bootstrap"),
            _section(key="substitute_products", title="Альтернативы", products=substitutes, source="product_substitutes", strategy="fastapi_bootstrap"),
        ],
        "request_id": request_id,
        "user_id": user_id,
    }


@app.get("/v1/recommendations/product/{product_id}/section/{section}")
def recommendations_product_section(
    product_id: int,
    section: str,
    limit: int = Query(default=8, ge=1, le=32),
    request_id: str = Query(default="", max_length=128),
    user_id: int = Query(default=0, ge=0),
) -> dict[str, object]:
    full = recommendations_product(product_id=product_id, limit=max(limit, 8), request_id=request_id, user_id=user_id)
    mapping = {
        "fbt": "accessory_products",
        "alternatives": "substitute_products",
        "seller_more": "similar_products",
    }
    target_key = mapping.get(section, section)
    sections = [item for item in full["sections"] if item["key"] == target_key]
    if not sections:
        sections = [_section(key=section, title="Рекомендации", products=full["sections"][0]["products"][:limit], source="generic", strategy="fastapi_bootstrap")]
    else:
        sections[0]["products"] = sections[0]["products"][:limit]
    return {
        "ok": True,
        "surface": "pdp",
        "variant": "control",
        "sections": sections,
    }


def _cart_like(payload: RecommendationSeedRequest, *, surface: str) -> dict[str, object]:
    seeds: list[dict] = []
    for product_id in payload.product_ids:
        item = _catalog_product(int(product_id))
        if item:
            seeds.append(item)
    exclude = {int(item.get("id") or 0) for item in seeds}
    cards: list[dict] = []
    for seed in seeds:
        cards.extend(_related_cards(seed, limit=payload.limit))
    cards.extend(_popular_cards(limit=max(payload.limit, 8)))
    ranked = _dedupe(cards, exclude=exclude, limit=payload.limit)
    return {
        "ok": True,
        "surface": surface,
        "variant": "control",
        "sections": [
            _section(
                key="cross_sell",
                title="Добавьте к заказу",
                products=ranked,
                source=f"{surface}_cross_sell",
                strategy="fastapi_bootstrap",
            )
        ],
        "request_id": payload.request_id,
        "user_id": payload.user_id,
    }


@app.post("/v1/recommendations/cart")
def recommendations_cart(payload: RecommendationSeedRequest) -> dict[str, object]:
    return _cart_like(payload, surface="cart")


@app.post("/v1/recommendations/checkout")
def recommendations_checkout(payload: RecommendationSeedRequest) -> dict[str, object]:
    return _cart_like(payload, surface="checkout")


@app.get("/v1/recommendations/reorder")
def recommendations_reorder(
    limit: int = Query(default=8, ge=1, le=32),
    request_id: str = Query(default="", max_length=128),
    user_id: int = Query(default=0, ge=0),
) -> dict[str, object]:
    products = _popular_cards(limit=limit)
    return {
        "ok": True,
        "surface": "reorder",
        "variant": "control",
        "sections": [_section(key="reorder", title="Повторить заказ", products=products, source="reorder", strategy="fastapi_bootstrap")],
        "request_id": request_id,
        "user_id": user_id,
    }


@app.get("/v1/recommendations/search-recovery")
def recommendations_search_recovery(
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=8, ge=1, le=32),
    request_id: str = Query(default="", max_length=128),
    user_id: int = Query(default=0, ge=0),
) -> dict[str, object]:
    rows = _catalog_products({"q": q, "limit": max(limit * 2, 12)}) if q.strip() else []
    cards = _dedupe([_card(item) for item in rows], limit=limit)
    if not cards:
        cards = _popular_cards(limit=limit)
    return {
        "ok": True,
        "surface": "catalog",
        "variant": "control",
        "sections": [
            _section(
                key="search_recovery",
                title="Возможно, вы искали",
                products=cards,
                source="search_recovery",
                strategy="fastapi_bootstrap",
            )
        ],
        "request_id": request_id,
        "user_id": user_id,
    }
