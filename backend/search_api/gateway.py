from __future__ import annotations

import logging
from collections import Counter
from decimal import Decimal

import httpx
from django.conf import settings

from catalog.api_contracts import product_card_payload
from catalog.selectors import ordered_products_with_related

log = logging.getLogger("search_api")


def _service_url() -> str:
    return str(getattr(settings, "SEARCH_SERVICE_URL", "http://search-api:8010")).strip().rstrip("/")


def _timeout() -> float:
    return float(getattr(settings, "SEARCH_SERVICE_TIMEOUT_SECONDS", 0.8))


def _request_id(request) -> str:
    return str(request.headers.get("X-Request-ID") or request.META.get("REQUEST_ID") or "").strip()


def _user_id(request) -> int:
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return 0
    return int(getattr(user, "id", 0) or 0)


def _product_ids(payload: dict[str, object]) -> list[int]:
    result: list[int] = []
    for raw in payload.get("product_ids") or []:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            result.append(value)
    return result


def _facets(products) -> dict[str, object]:
    brand_counts: Counter[tuple[int, str]] = Counter()
    category_counts: Counter[tuple[int, str]] = Counter()
    prices: list[Decimal] = []
    in_stock = 0
    out_of_stock = 0
    for product in products:
        brand = getattr(product, "brand", None)
        category = getattr(product, "category", None)
        if brand and brand.id:
            brand_counts[(int(brand.id), brand.name or "")] += 1
        if category and category.id:
            category_counts[(int(category.id), category.name or "")] += 1
        if int(getattr(product, "display_stock_qty", product.stock_qty) or 0) > 0:
            in_stock += 1
        else:
            out_of_stock += 1
        try:
            prices.append(Decimal(str(getattr(product, "display_price", product.price))))
        except (TypeError, ValueError, ArithmeticError):
            continue
    return {
        "brands": [{"id": item[0][0], "label": item[0][1], "count": item[1]} for item in brand_counts.most_common(12)],
        "categories": [{"id": item[0][0], "label": item[0][1], "count": item[1]} for item in category_counts.most_common(12)],
        "availability": {"in_stock": in_stock, "out_of_stock": out_of_stock},
        "price": {"min": f"{min(prices):.2f}" if prices else "0.00", "max": f"{max(prices):.2f}" if prices else "0.00"},
    }


def _remote(path: str, *, params: dict[str, object]) -> dict[str, object]:
    with httpx.Client(timeout=_timeout()) as client:
        response = client.get(f"{_service_url()}{path}", params=params)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict) or not payload.get("ok"):
        raise RuntimeError("search service returned malformed payload")
    return payload


def query_contract(*, query: str, limit: int, country_limit: int, request) -> dict[str, object]:
    params = {"q": query, "limit": limit, "country_limit": country_limit, "request_id": _request_id(request), "user_id": _user_id(request)}
    try:
        payload = _remote("/v1/search/query", params=params)
        ids = _product_ids(payload)[:limit]
        products = ordered_products_with_related(ids, include_rating=True)
        payload["product_ids"] = ids
        payload["products"] = [product_card_payload(product) for product in products]
        payload["facets"] = _facets(products)
        payload["source"] = "fastapi"
        payload["service_source"] = "search-api"
        return payload
    except Exception as exc:
        log.warning("search_service_degraded", extra={"query": query, "reason": str(exc)})
        return {
            "ok": True,
            "query": query,
            "effective_query": query,
            "rewritten_query": "",
            "rewrite_kind": "",
            "provider": "degraded",
            "product_ids": [],
            "products": [],
            "suggestions": [],
            "corrections": [],
            "countries": [],
            "facets": _facets([]),
            "source": "degraded",
            "service_source": "search-api",
            "service_error": type(exc).__name__,
        }


def suggestions_contract(*, query: str, limit: int, country_limit: int, request) -> dict[str, object]:
    params = {"q": query, "limit": limit, "country_limit": country_limit, "request_id": _request_id(request), "user_id": _user_id(request)}
    try:
        payload = _remote("/v1/search/suggestions", params=params)
        payload["source"] = "fastapi"
        payload["service_source"] = "search-api"
        return payload
    except Exception as exc:
        log.warning("search_suggestions_service_degraded", extra={"query": query, "reason": str(exc)})
        return {
            "ok": True,
            "query": query,
            "provider": "degraded",
            "effective_query": query,
            "rewritten_query": "",
            "rewrite_kind": "",
            "suggestions": [],
            "corrections": [],
            "countries": [],
            "source": "degraded",
            "service_source": "search-api",
            "service_error": type(exc).__name__,
        }
