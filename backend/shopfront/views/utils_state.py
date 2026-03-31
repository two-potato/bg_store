"""State, compare, ratings, and list helpers for shopfront views."""

from __future__ import annotations

from django.conf import settings
from django.db.models import Avg, Count, FloatField, Value
from django.db.models.functions import Coalesce
from django.http import Http404

from catalog.models import Product, ProductReview
from commerce.models import SellerStore, StoreReview

from ..cart_checkout_service import session_cart as _cart
from ..cart_store import persist_cart_for_user
from ..models import SavedList, SavedListItem
from ..recommendation.heuristics import record_recent_view, recently_viewed_ids_for_user
from ..recommendation.service import product_section_context
from .constants import COMPARE_LIMIT, COMPARE_SESSION_KEY
from .utils_catalog import _cache_get, _cache_set, _seller_store_for_user


def _product_recommendation_section(product: Product, section: str) -> dict:
    """Resolve recommendation section payload for product detail tabs."""
    try:
        return product_section_context(product, section)
    except ValueError as exc:
        raise Http404("Unknown recommendation section") from exc


def _record_recently_viewed(request, product: Product, limit: int = 12) -> None:
    """Persist recently viewed product to session and durable history."""
    key = "recently_viewed_products"
    existing = [int(pid) for pid in request.session.get(key, []) if str(pid).isdigit()]
    existing = [pid for pid in existing if pid != product.id]
    request.session[key] = [product.id] + existing[: max(0, limit - 1)]
    request.session.modified = True
    record_recent_view(request.user, product, limit=max(limit, 24))


def _recently_viewed_products(request, exclude_product_id: int | None = None, limit: int = 8):
    """Return recently viewed product objects ordered by recency."""
    from ..catalog_selectors import ordered_products_with_related as _ordered_products_with_related

    ids = [int(pid) for pid in request.session.get("recently_viewed_products", []) if str(pid).isdigit()]
    if request.user.is_authenticated:
        persistent_ids = recently_viewed_ids_for_user(request.user, limit=max(limit * 2, 12))
        ids = ids + [pid for pid in persistent_ids if pid not in ids]
    if exclude_product_id is not None:
        ids = [pid for pid in ids if pid != exclude_product_id]
    return _ordered_products_with_related(ids[:limit], include_rating=True)


def _cached_id_list(cache_key: str, ttl: int, builder) -> list[int]:
    """Return cached integer id list from a builder callback."""
    ids = _cache_get(cache_key)
    if ids is None:
        ids = list(builder())
        _cache_set(cache_key, ids, timeout=ttl)
    return [int(pid) for pid in ids if str(pid).isdigit()]


def _seller_rating_summary(seller_id: int | None) -> dict:
    """Return aggregate rating summary for products of one seller."""
    if not seller_id:
        return {"rating_avg": 0, "rating_count": 0}
    cache_key = f"shopfront:seller_rating:v1:{seller_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    agg = ProductReview.objects.filter(product__seller_id=seller_id).aggregate(
        rating_avg=Coalesce(Avg("rating"), Value(0.0), output_field=FloatField()),
        rating_count=Count("id"),
    )
    payload = {
        "rating_avg": agg["rating_avg"] or 0,
        "rating_count": agg["rating_count"] or 0,
    }
    _cache_set(cache_key, payload, timeout=getattr(settings, "CACHE_TTL_PDP_SUMMARY", 300))
    return payload


def _store_rating_summary(store: SellerStore | None) -> dict:
    """Return aggregate rating summary for a seller store."""
    if store is None:
        return {"rating_avg": 0, "rating_count": 0}
    cache_key = f"shopfront:store_rating:v1:{store.id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    agg = StoreReview.objects.filter(store=store).aggregate(
        rating_avg=Coalesce(Avg("rating"), Value(0.0), output_field=FloatField()),
        rating_count=Count("id"),
    )
    payload = {
        "rating_avg": agg["rating_avg"] or 0,
        "rating_count": agg["rating_count"] or 0,
    }
    _cache_set(cache_key, payload, timeout=getattr(settings, "CACHE_TTL_PDP_SUMMARY", 300))
    return payload


def _store_reviews_context(store: SellerStore, user):
    """Build store reviews context for vendor/store detail pages."""
    reviews_qs = store.reviews.select_related("user", "user__profile")
    agg = reviews_qs.aggregate(avg=Avg("rating"), count=Count("id"))
    user_review = reviews_qs.filter(user=user).first() if getattr(user, "is_authenticated", False) else None
    return {
        "store": store,
        "store_reviews": reviews_qs[:20],
        "store_rating_avg": agg["avg"] or 0,
        "store_rating_count": agg["count"] or 0,
        "store_user_review": user_review,
    }


def _compare_ids(request) -> list[int]:
    """Return normalized product ids from compare session state."""
    ids: list[int] = []
    for raw_id in request.session.get(COMPARE_SESSION_KEY, []) or []:
        try:
            product_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if product_id not in ids:
            ids.append(product_id)
    return ids[:COMPARE_LIMIT]


def _set_compare_ids(request, product_ids: list[int]) -> list[int]:
    """Store normalized compare ids in session and return persisted value."""
    normalized: list[int] = []
    for product_id in product_ids:
        try:
            candidate = int(product_id)
        except (TypeError, ValueError):
            continue
        if candidate not in normalized:
            normalized.append(candidate)
    request.session[COMPARE_SESSION_KEY] = normalized[:COMPARE_LIMIT]
    request.session.modified = True
    return request.session[COMPARE_SESSION_KEY]


def _compare_fields(products: list[Product]) -> list[dict]:
    """Build compare table rows for a list of products."""
    attribute_keys: list[str] = []
    seen_keys: set[str] = set()
    for product in products:
        for key in (product.attributes or {}).keys():
            if key in seen_keys:
                continue
            seen_keys.add(key)
            attribute_keys.append(key)

    rows = [
        {"label": "Цена", "values": [f"{product.display_price} ₽" for product in products]},
        {"label": "Бренд", "values": [getattr(product.brand, "name", "—") or "—" for product in products]},
        {"label": "Серия", "values": [getattr(product.series, "name", "—") or "—" for product in products]},
        {"label": "Категория", "values": [getattr(product.category, "name", "—") or "—" for product in products]},
        {"label": "Магазин", "values": [getattr(_seller_store_for_user(getattr(product, "seller", None)), "name", "—") or "—" for product in products]},
        {
            "label": "Рейтинг",
            "values": [
                f"{product.rating_avg:.1f} / 5 ({product.rating_count})" if getattr(product, "rating_count", 0) else "Нет оценок"
                for product in products
            ],
        },
        {"label": "Наличие", "values": [str(product.display_stock_qty) if product.display_stock_qty > 0 else "Нет в наличии" for product in products]},
        {"label": "MOQ", "values": [f"от {product.display_min_order_qty} {product.unit}" for product in products]},
        {
            "label": "Срок поставки",
            "values": [f"{product.display_lead_time_days} дн." if product.display_lead_time_days else "1-2 дня" for product in products],
        },
        {
            "label": "Фото",
            "values": [
                f"{len(getattr(product, 'prefetched_images', []) or [])} шт."
                if getattr(product, "prefetched_images", None)
                else "Нет"
                for product in products
            ],
        },
        {
            "label": "Документы",
            "values": [
                "Есть" if list(product.documents.all()) else "Нет"
                for product in products
            ],
        },
        {"label": "Упаковка", "values": [f"{product.pack_qty} {product.unit}" for product in products]},
        {"label": "Материал", "values": [product.material or "—" for product in products]},
        {"label": "Объём", "values": [f"{product.volume_ml} мл" if product.volume_ml else "—" for product in products]},
    ]
    for key in attribute_keys:
        rows.append(
            {
                "label": key,
                "values": [str((product.attributes or {}).get(key, "—") or "—") for product in products],
            }
        )
    for row in rows:
        normalized = {str(value).strip() for value in row["values"]}
        row["is_diff"] = len(normalized) > 1
    return rows


def _cart_add_product(request, product_id: int, qty: int = 1) -> int:
    """Add product quantity to cart session and persist for authenticated users."""
    cart = _cart(request)
    key = str(product_id)
    current = cart.get(key, {})
    current_qty = max(0, int(current.get("qty", 0) or 0))
    cart[key] = {"qty": current_qty + max(1, int(qty or 1))}
    request.session["cart"] = cart
    request.session.modified = True
    persist_cart_for_user(request.user, request.session.get("cart", {}))
    return cart[key]["qty"]


def _saved_list_queryset(user):
    """Return saved lists queryset with product previews prefetched."""
    return SavedList.objects.filter(user=user).prefetch_related("items__product__images").order_by("-updated_at", "-id")


def _saved_list_add_products(saved_list: SavedList, product_ids: list[int], quantities: dict[int, int] | None = None) -> int:
    """Add products into saved list while upserting quantity and ordering."""
    quantities = quantities or {}
    added = 0
    existing = {
        item.product_id: item for item in SavedListItem.objects.filter(saved_list=saved_list, product_id__in=product_ids)
    }
    for ordering, product_id in enumerate(product_ids, start=1):
        qty = max(1, int(quantities.get(product_id, 1) or 1))
        item = existing.get(product_id)
        if item:
            item.quantity = qty
            item.ordering = min(item.ordering or ordering, ordering)
            item.save(update_fields=["quantity", "ordering", "updated_at"])
            continue
        SavedListItem.objects.create(
            saved_list=saved_list,
            product_id=product_id,
            quantity=qty,
            ordering=ordering,
        )
        added += 1
    return added
