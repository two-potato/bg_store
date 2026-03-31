"""Contract layer for `/api/search/*` endpoints."""

from __future__ import annotations

import logging
from collections import Counter
from decimal import Decimal

import httpx
from django.conf import settings

from shopfront.api_contract_common import normalize_product_card, product_card_payload

from ..catalog_selectors import ordered_products_with_related
from .service import DatabaseSearchProvider, SearchBundle, get_search_provider, suggest_query_corrections

log = logging.getLogger("shopfront")


def _service_mode() -> str:
    return str(getattr(settings, "SEARCH_SERVICE_MODE", "django-inline")).strip().lower()


def _service_url() -> str:
    return str(getattr(settings, "SEARCH_SERVICE_URL", "http://search-api:8010")).strip().rstrip("/")


def _service_timeout() -> float:
    return float(getattr(settings, "SEARCH_SERVICE_TIMEOUT_SECONDS", 0.8))


def _search_facets(products) -> dict[str, object]:
    brand_counts: Counter[tuple[int, str]] = Counter()
    category_counts: Counter[tuple[int, str]] = Counter()
    in_stock = 0
    out_of_stock = 0
    prices: list[Decimal] = []

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
        except Exception:
            continue

    return {
        "brands": [
            {"id": brand_id, "label": label, "count": count}
            for (brand_id, label), count in brand_counts.most_common(12)
        ],
        "categories": [
            {"id": category_id, "label": label, "count": count}
            for (category_id, label), count in category_counts.most_common(12)
        ],
        "availability": {
            "in_stock": in_stock,
            "out_of_stock": out_of_stock,
        },
        "price": {
            "min": f"{min(prices):.2f}" if prices else "0.00",
            "max": f"{max(prices):.2f}" if prices else "0.00",
        },
    }


def _local_bundle(query: str, *, limit: int, country_limit: int) -> SearchBundle:
    provider = get_search_provider(prefer_semantic=True)
    try:
        bundle = provider.live_bundle(query=query, limit=limit, country_limit=country_limit)
    except Exception as exc:
        log.warning("search_contract_provider_failed", extra={"query": query, "reason": str(exc)})
        bundle = DatabaseSearchProvider().live_bundle(query=query, limit=limit, country_limit=country_limit)
    return bundle


def _local_query_contract(*, query: str, limit: int, country_limit: int) -> dict[str, object]:
    bundle = _local_bundle(query=query, limit=limit, country_limit=country_limit)
    products = ordered_products_with_related(bundle.product_ids[:limit], include_rating=True)
    cards = [product_card_payload(product) for product in products]
    corrections = suggest_query_corrections(query, limit=min(6, max(1, limit)))

    return {
        "ok": True,
        "query": query,
        "effective_query": str(getattr(bundle, "effective_query", "") or query),
        "rewritten_query": str(getattr(bundle, "rewritten_query", "") or ""),
        "rewrite_kind": str(getattr(bundle, "rewrite_kind", "") or ""),
        "provider": str(getattr(bundle, "provider", "unknown") or "unknown"),
        "product_ids": [int(product_id) for product_id in (bundle.product_ids[:limit] or [])],
        "products": cards,
        "suggestions": [str(item) for item in (bundle.suggestions or [])[: max(limit, 10)]],
        "corrections": [str(item) for item in corrections],
        "countries": [str(item) for item in (bundle.countries or [])[: max(country_limit, 0)]],
        "facets": _search_facets(products),
    }


def _local_suggestions_contract(*, query: str, limit: int, country_limit: int) -> dict[str, object]:
    bundle = _local_bundle(query=query, limit=limit, country_limit=country_limit)
    corrections = suggest_query_corrections(query, limit=min(6, max(1, limit)))
    return {
        "ok": True,
        "query": query,
        "provider": str(getattr(bundle, "provider", "unknown") or "unknown"),
        "effective_query": str(getattr(bundle, "effective_query", "") or query),
        "rewritten_query": str(getattr(bundle, "rewritten_query", "") or ""),
        "rewrite_kind": str(getattr(bundle, "rewrite_kind", "") or ""),
        "suggestions": [str(item) for item in (bundle.suggestions or [])[: max(limit, 10)]],
        "corrections": [str(item) for item in corrections],
        "countries": [str(item) for item in (bundle.countries or [])[: max(country_limit, 0)]],
    }


def _request_id(request) -> str:
    if request is None:
        return ""
    return str(
        request.headers.get("X-Request-ID")
        or request.META.get("HTTP_X_REQUEST_ID")
        or request.META.get("REQUEST_ID")
        or ""
    ).strip()


def _user_id(request) -> int:
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return 0
    return int(getattr(user, "id", 0) or 0)


def _remote_query_contract(*, query: str, limit: int, country_limit: int, request=None) -> dict[str, object]:
    params = {
        "q": query,
        "limit": limit,
        "country_limit": country_limit,
        "request_id": _request_id(request),
        "user_id": _user_id(request),
    }
    with httpx.Client(timeout=_service_timeout()) as client:
        response = client.get(f"{_service_url()}/v1/search/query", params=params)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict) or not payload.get("ok"):
        raise RuntimeError("search fastapi payload malformed")
    payload["products"] = [normalize_product_card(item) for item in (payload.get("products") or []) if isinstance(item, dict)]
    normalized_ids: list[int] = []
    for value in (payload.get("product_ids") or []):
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            normalized_ids.append(parsed)
    payload["product_ids"] = normalized_ids
    return payload


def _remote_suggestions_contract(*, query: str, limit: int, country_limit: int, request=None) -> dict[str, object]:
    params = {
        "q": query,
        "limit": limit,
        "country_limit": country_limit,
        "request_id": _request_id(request),
        "user_id": _user_id(request),
    }
    with httpx.Client(timeout=_service_timeout()) as client:
        response = client.get(f"{_service_url()}/v1/search/suggestions", params=params)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict) or not payload.get("ok"):
        raise RuntimeError("search suggestions fastapi payload malformed")
    return payload


def search_query_contract(
    *,
    query: str,
    limit: int = 24,
    country_limit: int = 6,
    request=None,
    mode_override: str | None = None,
) -> dict[str, object]:
    mode = (mode_override or _service_mode()).strip().lower()
    if mode == "fastapi":
        try:
            payload = _remote_query_contract(query=query, limit=limit, country_limit=country_limit, request=request)
            payload["engine_source"] = str(payload.get("source") or payload.get("engine_source") or "")
            payload["service_source"] = str(payload.get("service_source") or "search-api")
            payload["source"] = "fastapi"
            return payload
        except Exception as exc:
            log.warning("search_contract_fastapi_fallback", extra={"query": query, "reason": str(exc)})
            payload = _local_query_contract(query=query, limit=limit, country_limit=country_limit)
            payload["source"] = "django-inline-fallback"
            payload["service_source"] = "search-api"
            payload["engine_source"] = "django-inline"
            payload["service_error"] = str(exc)
            return payload
    payload = _local_query_contract(query=query, limit=limit, country_limit=country_limit)
    payload["source"] = "django-inline"
    payload["engine_source"] = "django-inline"
    return payload


def search_suggestions_contract(
    *,
    query: str,
    limit: int = 10,
    country_limit: int = 6,
    request=None,
    mode_override: str | None = None,
) -> dict[str, object]:
    mode = (mode_override or _service_mode()).strip().lower()
    if mode == "fastapi":
        try:
            payload = _remote_suggestions_contract(query=query, limit=limit, country_limit=country_limit, request=request)
            payload["engine_source"] = str(payload.get("source") or payload.get("engine_source") or "")
            payload["service_source"] = str(payload.get("service_source") or "search-api")
            payload["source"] = "fastapi"
            return payload
        except Exception as exc:
            log.warning("search_suggestions_fastapi_fallback", extra={"query": query, "reason": str(exc)})
            payload = _local_suggestions_contract(query=query, limit=limit, country_limit=country_limit)
            payload["source"] = "django-inline-fallback"
            payload["service_source"] = "search-api"
            payload["engine_source"] = "django-inline"
            payload["service_error"] = str(exc)
            return payload
    payload = _local_suggestions_contract(query=query, limit=limit, country_limit=country_limit)
    payload["source"] = "django-inline"
    payload["engine_source"] = "django-inline"
    return payload
