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
    country_name = product.country_of_origin.name if product.country_of_origin else ""
    tags = list(product.tags.values_list("name", flat=True)[:20]) if getattr(product, "pk", None) else []
    series_name = product.series.name if product.series else ""
    search_terms = _compact_terms(
        [
            product.name,
            product.sku,
            product.manufacturer_sku,
            product.barcode,
            product.brand.name if product.brand else "",
            series_name,
            product.category.name if product.category else "",
            country_name,
            product.material,
            product.purpose,
            product.flavor,
            store.name if store else "",
            product.seller.username if product.seller else "",
            *tags,
        ]
    )
    suggest_inputs = _compact_terms(
        [
            product.name,
            f"{product.brand.name} {product.name}" if product.brand else product.name,
            f"{product.category.name} {product.name}" if product.category else product.name,
            f"{store.name} {product.name}" if store else product.name,
            product.sku,
            *tags,
        ]
    )
    return {
        "id": product.id,
        "name": product.name,
        "sku": product.sku,
        "manufacturer_sku": product.manufacturer_sku or "",
        "barcode": product.barcode or "",
        "brand": product.brand.name if product.brand else "",
        "series": series_name,
        "category": product.category.name if product.category else "",
        "country_of_origin": country_name,
        "country_of_origin_keyword": (country_name or "").lower(),
        "store_name": store.name if store else "",
        "store_description": store.description if store else "",
        "seller_username": product.seller.username if product.seller else "",
        "material": product.material or "",
        "purpose": product.purpose or "",
        "flavor": product.flavor or "",
        "tags": tags,
        "description": product.description or "",
        "price": float(product.price or 0),
        "is_new": bool(product.is_new),
        "is_promo": bool(product.is_promo),
        "in_stock": int(product.stock_qty or 0) > 0,
        "search_terms": search_terms,
        "suggest": {
            "input": suggest_inputs,
            "weight": 10 + (2 if bool(product.is_new) else 0) + (1 if bool(product.is_promo) else 0),
        },
    }


def upsert_product(product):
    url = f"{_es_url()}/{_es_index()}/_doc/{product.id}"
    try:
        r = requests.put(url, json=product_doc(product), timeout=_timeout())
        r.raise_for_status()
    except Exception as exc:
        log.warning("es_upsert_failed", extra={"product_id": product.id, "reason": str(exc)})


def delete_product(product_id: int):
    url = f"{_es_url()}/{_es_index()}/_doc/{product_id}"
    try:
        r = requests.delete(url, timeout=_timeout())
        if r.status_code not in (200, 202, 404):
            r.raise_for_status()
    except Exception as exc:
        log.warning("es_delete_failed", extra={"product_id": product_id, "reason": str(exc)})
