"""Contract layer for `/api/recommendations/*` endpoints."""

from __future__ import annotations

import json
import logging
import time
from uuid import uuid4

import httpx
from django.conf import settings
from django.contrib.auth import get_user_model

from catalog.models import Product
from shopfront.api_contract_common import load_products_by_ids, normalize_product_card, product_card_payload

from .service import (
    cart_recommendations,
    checkout_recommendations,
    home_recommendations_context,
    product_detail_recommendations,
    product_section_context,
    reorder_recommendations,
    search_recovery_recommendations,
)

log = logging.getLogger("shopfront")


def _new_contract_id() -> str:
    return uuid4().hex


def _elapsed_ms(started_at: float) -> int:
    return max(0, int(round((time.perf_counter() - started_at) * 1000)))


def _service_mode() -> str:
    return str(getattr(settings, "RECOMMENDATION_SERVICE_MODE", "django-inline")).strip().lower()


def _service_url() -> str:
    return str(getattr(settings, "RECOMMENDATION_SERVICE_URL", "http://recommendation-api:8011")).strip().rstrip("/")


def _service_timeout() -> float:
    return float(getattr(settings, "RECOMMENDATION_SERVICE_TIMEOUT_SECONDS", 0.8))


def _section(*, key: str, title: str, products, tracking_payload: str = "", source: str = "", strategy: str = "") -> dict[str, object]:
    return {
        "key": key,
        "title": title,
        "source": source,
        "strategy": strategy,
        "tracking_payload": tracking_payload,
        "products": [product_card_payload(product) for product in products],
    }


def _decorate_tracking_payload(
    raw_payload: str,
    *,
    recommendation_id: str,
    impression_id: str,
    fallback_source: str,
    empty_reason: str,
    engine_source: str,
    service_source: str,
    latency_ms: int,
) -> str:
    if not raw_payload:
        return ""
    try:
        payload = json.loads(raw_payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return raw_payload
    if not isinstance(payload, dict):
        return raw_payload
    payload.setdefault("recommendation_id", recommendation_id)
    payload.setdefault("impression_id", impression_id)
    payload.setdefault("engine_source", engine_source)
    payload.setdefault("service_source", service_source)
    payload.setdefault("latency_ms", int(latency_ms))
    if fallback_source:
        payload.setdefault("fallback_source", fallback_source)
    if empty_reason:
        payload.setdefault("empty_reason", empty_reason)
    ecommerce = payload.get("ecommerce")
    if isinstance(ecommerce, dict):
        items = ecommerce.get("items")
        if isinstance(items, list):
            for item in items[:12]:
                if not isinstance(item, dict):
                    continue
                item.setdefault("recommendation_id", recommendation_id)
                item.setdefault("impression_id", impression_id)
    return json.dumps(payload, ensure_ascii=False)


def _finalize_payload(payload: dict[str, object], *, latency_ms: int, fallback_source: str = "") -> dict[str, object]:
    recommendation_id = str(payload.get("recommendation_id") or _new_contract_id())
    engine_source = str(payload.get("engine_source") or payload.get("source") or "django-inline")
    service_source = str(payload.get("service_source") or engine_source or "django-inline")
    sections = []
    has_products = False
    for raw_section in (payload.get("sections") or []):
        if not isinstance(raw_section, dict):
            continue
        section = dict(raw_section)
        products = list(section.get("products") or [])
        has_products = has_products or bool(products)
        impression_id = str(section.get("impression_id") or _new_contract_id())
        section_fallback_source = str(section.get("fallback_source") or fallback_source or "")
        section_empty_reason = str(section.get("empty_reason") or ("no_products" if not products else ""))
        section["impression_id"] = impression_id
        section["fallback_source"] = section_fallback_source
        section["empty_reason"] = section_empty_reason
        section["tracking_payload"] = _decorate_tracking_payload(
            str(section.get("tracking_payload") or ""),
            recommendation_id=recommendation_id,
            impression_id=impression_id,
            fallback_source=section_fallback_source,
            empty_reason=section_empty_reason,
            engine_source=engine_source,
            service_source=service_source,
            latency_ms=int(payload.get("latency_ms") or latency_ms),
        )
        sections.append(section)
    resolved_empty_reason = str(payload.get("empty_reason") or "")
    if not resolved_empty_reason:
        if payload.get("error") == "authentication_required":
            resolved_empty_reason = "authentication_required"
        elif payload.get("error") == "product_not_found":
            resolved_empty_reason = "product_not_found"
        elif not has_products:
            resolved_empty_reason = "all_sections_empty"
    payload["recommendation_id"] = recommendation_id
    payload["latency_ms"] = int(payload.get("latency_ms") or latency_ms)
    payload["engine_source"] = engine_source
    payload["service_source"] = service_source
    payload["fallback_source"] = str(payload.get("fallback_source") or fallback_source or "")
    payload["empty_reason"] = resolved_empty_reason
    payload["sections"] = sections
    return payload


def _resolve_user(request, *, user_id_override: int | None = None):
    if user_id_override:
        try:
            return get_user_model().objects.filter(id=int(user_id_override)).first()
        except (TypeError, ValueError):
            pass
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return user
    return None


def _request_id(request) -> str:
    if request is None:
        return ""
    return str(
        request.headers.get("X-Request-ID")
        or request.META.get("HTTP_X_REQUEST_ID")
        or request.META.get("REQUEST_ID")
        or ""
    ).strip()


def _local_home(*, request, limit: int, user_id_override: int | None = None) -> dict[str, object]:
    user = _resolve_user(request, user_id_override=user_id_override)
    context = home_recommendations_context(user, request=request, limit=limit)
    return {
        "ok": True,
        "surface": "home",
        "variant": str(context.get("recommendation_experiment_variant", "control")),
        "sections": [
            _section(
                key="recommended_for_you",
                title="Рекомендуем для вас",
                products=context.get("recommended_for_you", []),
                tracking_payload=str(context.get("recommended_for_you_tracking_payload", "")),
                source="home_for_you",
                strategy="materialized_or_ranked",
            ),
            _section(
                key="recently_viewed",
                title="Вы смотрели",
                products=context.get("home_recently_viewed", []),
                tracking_payload=str(context.get("home_recently_viewed_tracking_payload", "")),
                source="home_recently_viewed",
                strategy="recent_history_session_aware",
            ),
            _section(
                key="watchlist",
                title="Из ваших подписок",
                products=context.get("watchlist_products", []),
                tracking_payload=str(context.get("watchlist_products_tracking_payload", "")),
                source="home_watchlist",
                strategy="materialized_or_ranked",
            ),
            _section(
                key="popular",
                title="Популярное",
                products=context.get("home_popular_products", []),
                tracking_payload=str(context.get("home_popular_products_tracking_payload", "")),
                source="home_popular",
                strategy="popularity_snapshot",
            ),
            _section(
                key="replenishment",
                title="Пора пополнить",
                products=context.get("home_replenishment_products", []),
                tracking_payload=str(context.get("home_replenishment_tracking_payload", "")),
                source="home_replenishment",
                strategy="replenishment_profile",
            ),
        ],
    }


def _local_product(*, request, product_id: int, limit: int, user_id_override: int | None = None) -> dict[str, object]:
    user = _resolve_user(request, user_id_override=user_id_override)
    product = Product.objects.select_related("brand", "category", "seller", "seller__seller_store").filter(id=product_id).first()
    if product is None:
        return {
            "ok": False,
            "surface": "pdp",
            "variant": "control",
            "sections": [],
            "error": "product_not_found",
        }
    context = product_detail_recommendations(product, user=user, request=request, limit=limit)
    return {
        "ok": True,
        "surface": "pdp",
        "variant": str(context.get("recommendation_experiment_variant", "control")),
        "sections": [
            _section(
                key="similar_products",
                title="Похожие товары",
                products=context.get("similar_products", []),
                source="product_similar",
                strategy="cached_ranked",
            ),
            _section(
                key="accessory_products",
                title="С этим товаром берут",
                products=context.get("accessory_products", []),
                source="product_accessories",
                strategy="cached_ranked",
            ),
            _section(
                key="substitute_products",
                title="Альтернативы",
                products=context.get("substitute_products", []),
                source="product_substitutes",
                strategy="cached_ranked",
            ),
        ],
    }


def _local_product_section(
    *,
    request,
    product_id: int,
    section: str,
    user_id_override: int | None = None,
) -> dict[str, object]:
    user = _resolve_user(request, user_id_override=user_id_override)
    product = Product.objects.select_related("brand", "category", "seller", "seller__seller_store").filter(id=product_id).first()
    if product is None:
        return {
            "ok": False,
            "surface": "pdp",
            "variant": "control",
            "sections": [],
            "error": "product_not_found",
        }
    context = product_section_context(product, section, user=user, request=request)
    return {
        "ok": True,
        "surface": "pdp",
        "variant": "control",
        "sections": [
            _section(
                key=str(section),
                title=str(context.get("title") or "Рекомендации"),
                products=context.get("products", []),
                tracking_payload=str(context.get("tracking_payload", "")),
                source=str(context.get("recommendation_source", "")),
                strategy="materialized_or_ranked",
            )
        ],
    }


def _local_cart_like(
    *,
    request,
    product_ids: list[int],
    limit: int,
    checkout: bool,
    user_id_override: int | None = None,
) -> dict[str, object]:
    user = _resolve_user(request, user_id_override=user_id_override)
    products = load_products_by_ids(product_ids)
    context = (
        checkout_recommendations(products, user=user, request=request, limit=limit)
        if checkout
        else cart_recommendations(products, user=user, request=request, limit=limit)
    )
    return {
        "ok": True,
        "surface": "checkout" if checkout else "cart",
        "variant": "control",
        "sections": [
            _section(
                key="cross_sell",
                title="Добавьте к заказу",
                products=context.get("products", []),
                tracking_payload=str(context.get("tracking_payload", "")),
                source="checkout_cross_sell" if checkout else "cart_cross_sell",
                strategy="multi_source_ranked",
            )
        ],
    }


def _local_reorder(*, request, limit: int, user_id_override: int | None = None) -> dict[str, object]:
    user = _resolve_user(request, user_id_override=user_id_override)
    if user is None:
        return {
            "ok": False,
            "surface": "reorder",
            "variant": "control",
            "sections": [],
            "error": "authentication_required",
        }
    products = reorder_recommendations(user, limit=limit)
    return {
        "ok": True,
        "surface": "reorder",
        "variant": "control",
        "sections": [
            _section(
                key="reorder",
                title="Повторить заказ",
                products=products,
                source="reorder",
                strategy="materialized_or_ranked",
            )
        ],
    }


def _local_search_recovery(
    *,
    request,
    query: str,
    limit: int,
    user_id_override: int | None = None,
) -> dict[str, object]:
    user = _resolve_user(request, user_id_override=user_id_override)
    context = search_recovery_recommendations(query, user=user, request=request, limit=limit)
    return {
        "ok": True,
        "surface": "catalog",
        "variant": str(context.get("variant", "control")),
        "sections": [
            _section(
                key="search_recovery",
                title="Возможно, вы искали",
                products=context.get("products", []),
                tracking_payload=str(context.get("tracking_payload", "")),
                source="search_recovery",
                strategy="hybrid_recovery",
            )
        ],
    }


def _normalize_remote_response(payload: dict[str, object]) -> dict[str, object]:
    sections = []
    for raw_section in (payload.get("sections") or []):
        if not isinstance(raw_section, dict):
            continue
        cards = [
            normalize_product_card(item)
            for item in (raw_section.get("products") or [])
            if isinstance(item, dict)
        ]
        sections.append(
            {
                "key": str(raw_section.get("key") or ""),
                "title": str(raw_section.get("title") or ""),
                "source": str(raw_section.get("source") or ""),
                "strategy": str(raw_section.get("strategy") or ""),
                "tracking_payload": str(raw_section.get("tracking_payload") or ""),
                "impression_id": str(raw_section.get("impression_id") or ""),
                "fallback_source": str(raw_section.get("fallback_source") or ""),
                "empty_reason": str(raw_section.get("empty_reason") or ""),
                "products": cards,
            }
        )
    return {
        "ok": bool(payload.get("ok", False)),
        "surface": str(payload.get("surface") or ""),
        "variant": str(payload.get("variant") or "control"),
        "recommendation_id": str(payload.get("recommendation_id") or ""),
        "fallback_source": str(payload.get("fallback_source") or ""),
        "empty_reason": str(payload.get("empty_reason") or ""),
        "latency_ms": int(payload.get("latency_ms") or 0),
        "service_source": str(payload.get("service_source") or ""),
        "engine_source": str(payload.get("engine_source") or ""),
        "sections": sections,
    }


def _remote_call(path: str, *, method: str = "GET", params: dict[str, object] | None = None, json_data: dict[str, object] | None = None) -> dict[str, object]:
    with httpx.Client(timeout=_service_timeout()) as client:
        response = client.request(method, f"{_service_url()}{path}", params=params, json=json_data)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("recommendation fastapi payload malformed")
    normalized = _normalize_remote_response(payload)
    if not normalized.get("ok"):
        raise RuntimeError("recommendation fastapi payload malformed")
    return normalized


def _remote_params(request, *, limit: int, user_id_override: int | None = None) -> dict[str, object]:
    user = _resolve_user(request, user_id_override=user_id_override)
    return {
        "limit": limit,
        "request_id": _request_id(request),
        "user_id": int(getattr(user, "id", 0) or 0),
    }


def recommendation_home_contract(
    *,
    request,
    limit: int = 8,
    mode_override: str | None = None,
    user_id_override: int | None = None,
) -> dict[str, object]:
    started_at = time.perf_counter()
    mode = (mode_override or _service_mode()).strip().lower()
    if mode == "fastapi":
        try:
            payload = _remote_call("/v1/recommendations/home", params=_remote_params(request, limit=limit, user_id_override=user_id_override))
            payload["engine_source"] = str(payload.get("source") or payload.get("engine_source") or "")
            payload["service_source"] = str(payload.get("service_source") or "recommendation-api")
            payload["source"] = "fastapi"
            return _finalize_payload(payload, latency_ms=_elapsed_ms(started_at))
        except Exception as exc:
            log.warning("recommendation_home_fastapi_fallback", extra={"reason": str(exc)})
            payload = _local_home(request=request, limit=limit, user_id_override=user_id_override)
            payload["source"] = "django-inline-fallback"
            payload["service_source"] = "recommendation-api"
            payload["engine_source"] = "django-inline"
            payload["service_error"] = str(exc)
            return _finalize_payload(payload, latency_ms=_elapsed_ms(started_at), fallback_source="remote_error")
    payload = _local_home(request=request, limit=limit, user_id_override=user_id_override)
    payload["source"] = "django-inline"
    payload["engine_source"] = "django-inline"
    return _finalize_payload(payload, latency_ms=_elapsed_ms(started_at))


def recommendation_product_contract(
    *,
    request,
    product_id: int,
    limit: int = 12,
    mode_override: str | None = None,
    user_id_override: int | None = None,
) -> dict[str, object]:
    started_at = time.perf_counter()
    mode = (mode_override or _service_mode()).strip().lower()
    if mode == "fastapi":
        try:
            params = _remote_params(request, limit=limit, user_id_override=user_id_override)
            payload = _remote_call(f"/v1/recommendations/product/{product_id}", params=params)
            payload["engine_source"] = str(payload.get("source") or payload.get("engine_source") or "")
            payload["service_source"] = str(payload.get("service_source") or "recommendation-api")
            payload["source"] = "fastapi"
            return _finalize_payload(payload, latency_ms=_elapsed_ms(started_at))
        except Exception as exc:
            log.warning("recommendation_product_fastapi_fallback", extra={"product_id": product_id, "reason": str(exc)})
            payload = _local_product(request=request, product_id=product_id, limit=limit, user_id_override=user_id_override)
            payload["source"] = "django-inline-fallback"
            payload["service_source"] = "recommendation-api"
            payload["engine_source"] = "django-inline"
            payload["service_error"] = str(exc)
            return _finalize_payload(payload, latency_ms=_elapsed_ms(started_at), fallback_source="remote_error")
    payload = _local_product(request=request, product_id=product_id, limit=limit, user_id_override=user_id_override)
    payload["source"] = "django-inline"
    payload["engine_source"] = "django-inline"
    return _finalize_payload(payload, latency_ms=_elapsed_ms(started_at))


def recommendation_product_section_contract(
    *,
    request,
    product_id: int,
    section: str,
    mode_override: str | None = None,
    user_id_override: int | None = None,
) -> dict[str, object]:
    started_at = time.perf_counter()
    mode = (mode_override or _service_mode()).strip().lower()
    if mode == "fastapi":
        try:
            params = _remote_params(request, limit=8, user_id_override=user_id_override)
            payload = _remote_call(f"/v1/recommendations/product/{product_id}/section/{section}", params=params)
            payload["engine_source"] = str(payload.get("source") or payload.get("engine_source") or "")
            payload["service_source"] = str(payload.get("service_source") or "recommendation-api")
            payload["source"] = "fastapi"
            return _finalize_payload(payload, latency_ms=_elapsed_ms(started_at))
        except Exception as exc:
            log.warning(
                "recommendation_product_section_fastapi_fallback",
                extra={"product_id": product_id, "section": section, "reason": str(exc)},
            )
            payload = _local_product_section(
                request=request,
                product_id=product_id,
                section=section,
                user_id_override=user_id_override,
            )
            payload["source"] = "django-inline-fallback"
            payload["service_source"] = "recommendation-api"
            payload["engine_source"] = "django-inline"
            payload["service_error"] = str(exc)
            return _finalize_payload(payload, latency_ms=_elapsed_ms(started_at), fallback_source="remote_error")
    payload = _local_product_section(request=request, product_id=product_id, section=section, user_id_override=user_id_override)
    payload["source"] = "django-inline"
    payload["engine_source"] = "django-inline"
    return _finalize_payload(payload, latency_ms=_elapsed_ms(started_at))


def recommendation_cart_contract(
    *,
    request,
    product_ids: list[int],
    limit: int = 8,
    checkout: bool = False,
    mode_override: str | None = None,
    user_id_override: int | None = None,
) -> dict[str, object]:
    started_at = time.perf_counter()
    mode = (mode_override or _service_mode()).strip().lower()
    if mode == "fastapi":
        try:
            body = {"product_ids": product_ids, **_remote_params(request, limit=limit, user_id_override=user_id_override)}
            path = "/v1/recommendations/checkout" if checkout else "/v1/recommendations/cart"
            payload = _remote_call(path, method="POST", json_data=body)
            payload["engine_source"] = str(payload.get("source") or payload.get("engine_source") or "")
            payload["service_source"] = str(payload.get("service_source") or "recommendation-api")
            payload["source"] = "fastapi"
            return _finalize_payload(payload, latency_ms=_elapsed_ms(started_at))
        except Exception as exc:
            log.warning("recommendation_cart_fastapi_fallback", extra={"checkout": checkout, "reason": str(exc)})
            payload = _local_cart_like(
                request=request,
                product_ids=product_ids,
                limit=limit,
                checkout=checkout,
                user_id_override=user_id_override,
            )
            payload["source"] = "django-inline-fallback"
            payload["service_source"] = "recommendation-api"
            payload["engine_source"] = "django-inline"
            payload["service_error"] = str(exc)
            return _finalize_payload(payload, latency_ms=_elapsed_ms(started_at), fallback_source="remote_error")
    payload = _local_cart_like(
        request=request,
        product_ids=product_ids,
        limit=limit,
        checkout=checkout,
        user_id_override=user_id_override,
    )
    payload["source"] = "django-inline"
    payload["engine_source"] = "django-inline"
    return _finalize_payload(payload, latency_ms=_elapsed_ms(started_at))


def recommendation_reorder_contract(
    *,
    request,
    limit: int = 8,
    mode_override: str | None = None,
    user_id_override: int | None = None,
) -> dict[str, object]:
    started_at = time.perf_counter()
    mode = (mode_override or _service_mode()).strip().lower()
    if mode == "fastapi":
        try:
            payload = _remote_call("/v1/recommendations/reorder", params=_remote_params(request, limit=limit, user_id_override=user_id_override))
            payload["engine_source"] = str(payload.get("source") or payload.get("engine_source") or "")
            payload["service_source"] = str(payload.get("service_source") or "recommendation-api")
            payload["source"] = "fastapi"
            return _finalize_payload(payload, latency_ms=_elapsed_ms(started_at))
        except Exception as exc:
            log.warning("recommendation_reorder_fastapi_fallback", extra={"reason": str(exc)})
            payload = _local_reorder(request=request, limit=limit, user_id_override=user_id_override)
            payload["source"] = "django-inline-fallback"
            payload["service_source"] = "recommendation-api"
            payload["engine_source"] = "django-inline"
            payload["service_error"] = str(exc)
            return _finalize_payload(payload, latency_ms=_elapsed_ms(started_at), fallback_source="remote_error")
    payload = _local_reorder(request=request, limit=limit, user_id_override=user_id_override)
    payload["source"] = "django-inline"
    payload["engine_source"] = "django-inline"
    return _finalize_payload(payload, latency_ms=_elapsed_ms(started_at))


def recommendation_search_recovery_contract(
    *,
    request,
    query: str,
    limit: int = 8,
    mode_override: str | None = None,
    user_id_override: int | None = None,
) -> dict[str, object]:
    started_at = time.perf_counter()
    mode = (mode_override or _service_mode()).strip().lower()
    if mode == "fastapi":
        try:
            params = _remote_params(request, limit=limit, user_id_override=user_id_override)
            params["q"] = query
            payload = _remote_call("/v1/recommendations/search-recovery", params=params)
            payload["engine_source"] = str(payload.get("source") or payload.get("engine_source") or "")
            payload["service_source"] = str(payload.get("service_source") or "recommendation-api")
            payload["source"] = "fastapi"
            return _finalize_payload(payload, latency_ms=_elapsed_ms(started_at))
        except Exception as exc:
            log.warning("recommendation_search_recovery_fastapi_fallback", extra={"query": query, "reason": str(exc)})
            payload = _local_search_recovery(request=request, query=query, limit=limit, user_id_override=user_id_override)
            payload["source"] = "django-inline-fallback"
            payload["service_source"] = "recommendation-api"
            payload["engine_source"] = "django-inline"
            payload["service_error"] = str(exc)
            return _finalize_payload(payload, latency_ms=_elapsed_ms(started_at), fallback_source="remote_error")
    payload = _local_search_recovery(request=request, query=query, limit=limit, user_id_override=user_id_override)
    payload["source"] = "django-inline"
    payload["engine_source"] = "django-inline"
    return _finalize_payload(payload, latency_ms=_elapsed_ms(started_at))
