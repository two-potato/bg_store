import logging
from typing import List
from decimal import Decimal

import requests
from django.conf import settings
from django.db.models import Avg

log = logging.getLogger("catalog")


def _es_url() -> str:
    return getattr(settings, "OPENSEARCH_URL", "http://opensearch:9200").rstrip("/")


def _es_index() -> str:
    return getattr(settings, "OPENSEARCH_PRODUCTS_INDEX", "products")


def _timeout() -> float:
    return float(getattr(settings, "OPENSEARCH_TIMEOUT_SECONDS", 0.8))


def _compact_terms(values: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw in values:
        v = " ".join(str(raw or "").strip().split())
        if not v:
            continue
        key = v.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


def product_doc(product):
    store = getattr(getattr(product, "seller", None), "seller_store", None)
    country = getattr(product, "country_of_origin", None)
    country_name = getattr(country, "name", "") if country else ""
    tags_manager = getattr(product, "tags", None)
    tags = list(tags_manager.values_list("name", flat=True)[:20]) if tags_manager is not None and getattr(product, "pk", None) else []
    tag_ids = list(tags_manager.values_list("id", flat=True)[:20]) if tags_manager is not None and getattr(product, "pk", None) else []
    series = getattr(product, "series", None)
    series_name = getattr(series, "name", "") if series else ""
    brand = getattr(product, "brand", None)
    category = getattr(product, "category", None)
    seller = getattr(product, "seller", None)
    store_reviews = getattr(store, "reviews", None)
    seller_rating = 0.0
    seller_review_count = 0
    if store_reviews is not None and hasattr(store_reviews, "aggregate"):
        review_summary = store_reviews.aggregate(avg_rating=Avg("rating"))
        seller_rating = float(review_summary.get("avg_rating") or 0)
        try:
            seller_review_count = int(store_reviews.count())
        except Exception:
            seller_review_count = 0
    collections_manager = getattr(product, "collections", None)
    collections = list(collections_manager.values_list("name", flat=True)[:20]) if collections_manager is not None and getattr(product, "pk", None) else []
    collection_ids = list(collections_manager.values_list("id", flat=True)[:20]) if collections_manager is not None and getattr(product, "pk", None) else []
    documents_manager = getattr(product, "documents", None)
    document_kinds = list(documents_manager.values_list("kind", flat=True)[:20]) if documents_manager is not None and getattr(product, "pk", None) else []
    stock_qty = int(getattr(product, "stock_qty", 0) or 0)
    lead_time_days = int(getattr(product, "lead_time_days", 0) or 0)
    min_order_qty = int(getattr(product, "min_order_qty", 1) or 1)
    pack_qty = int(getattr(product, "pack_qty", 1) or 1)
    price = float(getattr(product, "price", 0) or 0)
    price_bucket = "premium" if price >= 10000 else "mid" if price >= 2000 else "entry"
    search_terms = _compact_terms(
        [
            getattr(product, "name", ""),
            getattr(product, "sku", ""),
            getattr(product, "manufacturer_sku", ""),
            getattr(product, "barcode", ""),
            getattr(brand, "name", "") if brand else "",
            series_name,
            getattr(category, "name", "") if category else "",
            country_name,
            getattr(product, "material", ""),
            getattr(product, "purpose", ""),
            getattr(product, "flavor", ""),
            store.name if store else "",
            getattr(seller, "username", "") if seller else "",
            *tags,
        ]
    )
    semantic_terms = _compact_terms(
        [
            getattr(product, "name", ""),
            getattr(brand, "name", "") if brand else "",
            getattr(category, "name", "") if category else "",
            getattr(product, "description", "") or "",
            getattr(product, "material", "") or "",
            getattr(product, "purpose", "") or "",
            getattr(product, "flavor", "") or "",
            *tags,
        ]
    )
    suggest_inputs = _compact_terms(
        [
            getattr(product, "name", ""),
            f"{brand.name} {getattr(product, 'name', '')}" if brand else getattr(product, "name", ""),
            f"{category.name} {getattr(product, 'name', '')}" if category else getattr(product, "name", ""),
            f"{store.name} {getattr(product, 'name', '')}" if store else getattr(product, "name", ""),
            getattr(product, "sku", ""),
            *tags,
        ]
    )
    return {
        "id": product.id,
        "name": getattr(product, "name", ""),
        "sku": getattr(product, "sku", ""),
        "manufacturer_sku": getattr(product, "manufacturer_sku", "") or "",
        "barcode": getattr(product, "barcode", "") or "",
        "brand": getattr(brand, "name", "") if brand else "",
        "brand_id": getattr(product, "brand_id", None),
        "series": series_name,
        "series_id": getattr(product, "series_id", None),
        "category": getattr(category, "name", "") if category else "",
        "category_id": getattr(product, "category_id", None),
        "country_of_origin": country_name,
        "country_of_origin_keyword": (country_name or "").lower(),
        "store_name": store.name if store else "",
        "store_description": store.description if store else "",
        "seller_username": getattr(seller, "username", "") if seller else "",
        "seller_id": getattr(product, "seller_id", None),
        "seller_rating": seller_rating,
        "seller_review_count": seller_review_count,
        "seller_is_verified": bool(store and getattr(store, "moderation_status", "") == "approved"),
        "material": getattr(product, "material", "") or "",
        "purpose": getattr(product, "purpose", "") or "",
        "flavor": getattr(product, "flavor", "") or "",
        "tags": tags,
        "tag_ids": tag_ids,
        "collections": collections,
        "collection_ids": collection_ids,
        "description": getattr(product, "description", "") or "",
        "price": price,
        "price_bucket": price_bucket,
        "is_new": bool(getattr(product, "is_new", False)),
        "is_promo": bool(getattr(product, "is_promo", False)),
        "in_stock": stock_qty > 0,
        "stock_qty": stock_qty,
        "min_order_qty": min_order_qty,
        "lead_time_days": lead_time_days,
        "has_fast_delivery": lead_time_days <= 2,
        "pack_qty": pack_qty,
        "unit": getattr(product, "unit", "") or "",
        "publication_status": getattr(product, "publication_status", "") or "",
        "has_documents": bool(document_kinds),
        "has_certificate": "certificate" in {str(kind or "") for kind in document_kinds},
        "procurement_fit_score": float(
            (Decimal("2") if bool(document_kinds) else Decimal("0"))
            + (Decimal("2") if min_order_qty <= 5 else Decimal("0"))
            + (Decimal("2") if lead_time_days <= 3 else Decimal("0"))
            + (Decimal("1") if stock_qty > 0 else Decimal("0"))
        ),
        "is_featured_collection_product": bool(collection_ids),
        "popularity_score_7d": float(getattr(product, "_popularity_score_7d", 0) or 0),
        "popularity_score_30d": float(getattr(product, "_popularity_score_30d", 0) or 0),
        "purchase_count_30d": int(getattr(product, "_purchase_count_30d", 0) or 0),
        "view_count_7d": int(getattr(product, "_view_count_7d", 0) or 0),
        "add_to_cart_count_7d": int(getattr(product, "_add_to_cart_count_7d", 0) or 0),
        "conversion_score": float(getattr(product, "_conversion_score", 0) or 0),
        "search_terms": search_terms,
        "semantic_terms": semantic_terms,
        "semantic_text": " | ".join(semantic_terms),
        "suggest": {
            "input": suggest_inputs,
            "weight": 10 + (2 if bool(getattr(product, "is_new", False)) else 0) + (1 if bool(getattr(product, "is_promo", False)) else 0),
        },
    }


def upsert_product(product):
    if not getattr(settings, "OPENSEARCH_ENABLED", True):
        return
    url = f"{_es_url()}/{_es_index()}/_doc/{product.id}"
    try:
        r = requests.put(url, json=product_doc(product), timeout=_timeout())
        r.raise_for_status()
    except requests.RequestException as exc:
        log.warning("opensearch_upsert_failed", extra={"product_id": product.id, "reason": str(exc)})


def delete_product(product_id: int):
    if not getattr(settings, "OPENSEARCH_ENABLED", True):
        return
    url = f"{_es_url()}/{_es_index()}/_doc/{product_id}"
    try:
        r = requests.delete(url, timeout=_timeout())
        if r.status_code not in (200, 202, 404):
            r.raise_for_status()
    except requests.RequestException as exc:
        log.warning("opensearch_delete_failed", extra={"product_id": product_id, "reason": str(exc)})
