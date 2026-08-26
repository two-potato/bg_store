from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from urllib.parse import urlencode

from django.http import JsonResponse

from catalog.models import Product
from commerce.cart_checkout import cart_summary


def money(value) -> str:
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    try:
        return f"{Decimal(str(value)):.2f}"
    except Exception:
        return str(value)


def request_payload(request) -> tuple[dict[str, object], str | None]:
    if "application/json" not in (request.content_type or "").lower():
        return request.POST.dict(), None
    if not request.body:
        return {}, None
    try:
        value = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}, "invalid_json"
    return (value, None) if isinstance(value, dict) else ({}, "invalid_json")


def read_int(payload: Mapping[str, object], field: str, default: int | None = None) -> int | None:
    raw = payload.get(field)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def string(raw, default: str = "") -> str:
    return default if raw is None else str(raw).strip()


def coerce_bool(raw, default: bool = False) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def login_target(request) -> str:
    path = request.path or "/"
    if path.startswith("/api/storefront/orders/"):
        parts = path.strip("/").split("/")
        if len(parts) >= 4 and parts[3].isdigit():
            return f"/account/orders/{parts[3]}/"
    if path.startswith("/api/storefront/account/"):
        return "/account/"
    if path.startswith("/api/storefront/cart"):
        return "/cart/"
    if path.startswith("/api/storefront/tools/favorites"):
        return "/account/favorites/"
    if path.startswith("/api/storefront/tools/lists/"):
        parts = path.strip("/").split("/")
        if len(parts) >= 5 and parts[4].isdigit():
            return f"/account/lists/{parts[4]}/"
        return "/account/lists/"
    if path.startswith("/api/storefront/tools/saved-searches"):
        return "/account/saved-searches/"
    return "/"


def json_error(request, error: str, status: int):
    payload: dict[str, object] = {"ok": False, "error": error}
    if error == "authentication_required":
        payload["login_url"] = f"/account/login/?{urlencode({'next': login_target(request)})}"
    return JsonResponse(payload, status=status)


def product_image_url(product: Product) -> str:
    prefetched = getattr(product, "prefetched_images", None) or []
    if prefetched:
        return prefetched[0].public_url
    image = product.images.order_by("ordering", "id").first()
    return image.public_url if image else ""


def product_card(product: Product, *, qty: int | None = None, item_id: int | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": product.id,
        "slug": product.slug,
        "sku": product.sku,
        "name": product.name,
        "image_url": product_image_url(product),
        "price": money(product.display_price),
        "stock_qty": int(product.display_stock_qty or 0),
        "min_order_qty": int(product.display_min_order_qty or 1),
        "brand_name": getattr(getattr(product, "brand", None), "name", "") or "",
    }
    if qty is not None:
        payload["qty"] = int(qty)
    if item_id is not None:
        payload["item_id"] = int(item_id)
    return payload


def cart_payload(request) -> dict[str, object]:
    ctx = cart_summary(request)
    def line(item):
        product = item["p"]
        store = item.get("seller_store")
        seller = getattr(product, "seller", None)
        return {
            "product": {**product_card(product), "brand": getattr(getattr(product, "brand", None), "name", "") or "", "category": getattr(getattr(product, "category", None), "name", "") or ""},
            "qty": int(item["qty"]),
            "row_total": money(item["row"]),
            "seller": {"id": getattr(store, "id", None) or getattr(seller, "id", None), "name": getattr(store, "name", "") or getattr(seller, "username", "") or "Servio", "slug": getattr(store, "slug", "") or ""},
        }
    items = [line(item) for item in ctx["items"]]
    return {
        "items": items,
        "seller_groups": [{"title": g["title"], "slug": g["slug"], "subtotal": money(g["subtotal"]), "items": [line(i) for i in g["items"]]} for g in ctx["seller_groups"]],
        "seller_count": int(ctx["seller_count"]),
        "cart_count": int(ctx["cart_count"]),
        "is_empty": not bool(items),
        "subtotal": money(ctx["subtotal"]),
        "discount_percent": money(ctx["discount_percent"]),
        "discount_amount": money(ctx["discount_amount"]),
        "coupon_discount_amount": money(ctx["coupon_discount_amount"]),
        "profile_discount_amount": money(ctx["profile_discount_amount"]),
        "total": money(ctx["total"]),
        "coupon": {"code": ctx["resolved_coupon_code"] or "", "validation_error": ctx["coupon_validation_error"] or ""},
    }
