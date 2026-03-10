import logging
from typing import List

import requests
from django.conf import settings

log = logging.getLogger("catalog")


def _es_url() -> str:
    return getattr(settings, "ES_URL", "http://es:9200").rstrip("/")


def _es_index() -> str:
    return getattr(settings, "ES_PRODUCTS_INDEX", "products")


def _timeout() -> float:
    return float(getattr(settings, "ES_TIMEOUT_SECONDS", 0.8))


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
    series = getattr(product, "series", None)
    series_name = getattr(series, "name", "") if series else ""
    brand = getattr(product, "brand", None)
    category = getattr(product, "category", None)
    seller = getattr(product, "seller", None)
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
        "series": series_name,
        "category": getattr(category, "name", "") if category else "",
        "country_of_origin": country_name,
        "country_of_origin_keyword": (country_name or "").lower(),
        "store_name": store.name if store else "",
        "store_description": store.description if store else "",
        "seller_username": getattr(seller, "username", "") if seller else "",
        "material": getattr(product, "material", "") or "",
        "purpose": getattr(product, "purpose", "") or "",
        "flavor": getattr(product, "flavor", "") or "",
        "tags": tags,
        "description": getattr(product, "description", "") or "",
        "price": float(getattr(product, "price", 0) or 0),
        "is_new": bool(getattr(product, "is_new", False)),
        "is_promo": bool(getattr(product, "is_promo", False)),
        "in_stock": int(getattr(product, "stock_qty", 0) or 0) > 0,
        "search_terms": search_terms,
        "semantic_terms": semantic_terms,
        "semantic_text": " | ".join(semantic_terms),
        "suggest": {
            "input": suggest_inputs,
            "weight": 10 + (2 if bool(getattr(product, "is_new", False)) else 0) + (1 if bool(getattr(product, "is_promo", False)) else 0),
        },
    }


def upsert_product(product):
    if not getattr(settings, "ES_ENABLED", True):
        return
    url = f"{_es_url()}/{_es_index()}/_doc/{product.id}"
    try:
        r = requests.put(url, json=product_doc(product), timeout=_timeout())
        r.raise_for_status()
    except Exception as exc:
        log.warning("es_upsert_failed", extra={"product_id": product.id, "reason": str(exc)})


def delete_product(product_id: int):
    if not getattr(settings, "ES_ENABLED", True):
        return
    url = f"{_es_url()}/{_es_index()}/_doc/{product_id}"
    try:
        r = requests.delete(url, timeout=_timeout())
        if r.status_code not in (200, 202, 404):
            r.raise_for_status()
    except Exception as exc:
        log.warning("es_delete_failed", extra={"product_id": product_id, "reason": str(exc)})
