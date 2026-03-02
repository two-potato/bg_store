import logging

import requests
from django.conf import settings

log = logging.getLogger("catalog")


def _es_url() -> str:
    return getattr(settings, "ES_URL", "http://es:9200").rstrip("/")


def _es_index() -> str:
    return getattr(settings, "ES_PRODUCTS_INDEX", "products")


def _timeout() -> float:
    return float(getattr(settings, "ES_TIMEOUT_SECONDS", 0.8))


def product_doc(product):
    return {
        "id": product.id,
        "name": product.name,
        "sku": product.sku,
        "brand": product.brand.name if product.brand else "",
        "category": product.category.name if product.category else "",
        "country_of_origin": product.country_of_origin.name if product.country_of_origin else "",
        "description": product.description or "",
        "price": float(product.price or 0),
        "is_new": bool(product.is_new),
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
