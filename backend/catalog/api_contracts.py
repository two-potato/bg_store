from __future__ import annotations

from decimal import Decimal

from catalog.models import Product
from catalog.selectors import ordered_products_with_related


def money(value: object) -> str:
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    try:
        return f"{Decimal(str(value)):.2f}"
    except Exception:
        return "0.00"


def product_image_url(product: Product) -> str:
    prefetched_images = getattr(product, "prefetched_images", None) or []
    if prefetched_images:
        return prefetched_images[0].public_url
    first = product.images.order_by("ordering", "id").only("url").first()
    return first.public_url if first else ""


def product_card_payload(product: Product) -> dict[str, object]:
    seller_store = getattr(getattr(product, "seller", None), "seller_store", None)
    return {
        "id": int(product.id),
        "slug": product.slug,
        "sku": product.sku,
        "name": product.name,
        "image_url": product_image_url(product),
        "price": money(getattr(product, "display_price", product.price)),
        "stock_qty": int(getattr(product, "display_stock_qty", product.stock_qty) or 0),
        "min_order_qty": int(getattr(product, "display_min_order_qty", product.min_order_qty) or 1),
        "brand_name": getattr(getattr(product, "brand", None), "name", "") or "",
        "seller_name": getattr(seller_store, "name", "") if seller_store else "",
        "rating_avg": float(getattr(product, "rating_avg", 0.0) or 0.0),
        "rating_count": int(getattr(product, "rating_count", 0) or 0),
        "is_new": bool(getattr(product, "is_new", False)),
        "is_promo": bool(getattr(product, "is_promo", False)),
    }


def normalize_product_card(raw: dict[str, object]) -> dict[str, object]:
    return {
        "id": int(raw.get("id") or 0),
        "slug": str(raw.get("slug") or ""),
        "sku": str(raw.get("sku") or ""),
        "name": str(raw.get("name") or ""),
        "image_url": str(raw.get("image_url") or ""),
        "price": money(raw.get("price") or "0"),
        "stock_qty": int(raw.get("stock_qty") or 0),
        "min_order_qty": int(raw.get("min_order_qty") or 1),
        "brand_name": str(raw.get("brand_name") or ""),
        "seller_name": str(raw.get("seller_name") or ""),
        "rating_avg": float(raw.get("rating_avg") or 0.0),
        "rating_count": int(raw.get("rating_count") or 0),
        "is_new": bool(raw.get("is_new") or False),
        "is_promo": bool(raw.get("is_promo") or False),
    }


def load_products_by_ids(product_ids: list[int]) -> list[Product]:
    normalized_ids: list[int] = []
    for value in product_ids:
        try:
            candidate = int(value)
        except (TypeError, ValueError):
            continue
        if candidate > 0:
            normalized_ids.append(candidate)
    return ordered_products_with_related(normalized_ids, include_rating=True)
