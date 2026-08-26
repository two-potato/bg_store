"""Analytics ingest views for first-party storefront feedback signals."""

from __future__ import annotations

import json

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from core.logging_utils import log_calls

from catalog.models import Product

from ..models import RecommendationEvent
from ..recommendation.attribution_service import (
    record_recommendation_event,
    remember_recommendation_feedback,
)
from ..recommendation.observability import observe_recommendation_event
from ..searching.attribution import remember_search_feedback
from ..searching.observability import observe_search_feedback_event
from .constants import log


def _safe_int(raw_value, default: int = 0) -> int:
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default


def _client_ip(request) -> str:
    forwarded_for = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    if forwarded_for and getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        return forwarded_for
    return request.META.get("REMOTE_ADDR", "unknown")


def _same_origin_or_allowed_host(request) -> bool:
    origin = (request.headers.get("Origin") or "").strip()
    if not origin:
        return True
    allowed_hosts = {
        request.get_host(),
        request.get_host().split(":")[0],
        *getattr(settings, "ALLOWED_HOSTS", []),
    }
    return url_has_allowed_host_and_scheme(origin, allowed_hosts=allowed_hosts, require_https=False)


def _ingest_throttled(request, *, scope: str) -> bool:
    limit = max(1, int(getattr(settings, "ANALYTICS_INGEST_RATE_LIMIT", 180)))
    window_seconds = max(1, int(getattr(settings, "ANALYTICS_INGEST_WINDOW_SECONDS", 60)))
    session_key = request.session.session_key or "anon"
    cache_key = f"shopfront:analytics:{scope}:{_client_ip(request)}:{session_key}"
    if cache.add(cache_key, 1, timeout=window_seconds):
        return False
    try:
        current = cache.incr(cache_key)
    except ValueError:
        current = int(cache.get(cache_key, 0) or 0) + 1
        cache.set(cache_key, current, timeout=window_seconds)
    return int(current) > limit


def _parse_json_payload(request):
    try:
        return json.loads((request.body or b"{}").decode("utf-8") or "{}"), None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, JsonResponse({"ok": False, "error": "invalid_json"}, status=400)


def _product_lookup_maps(raw_items: list[dict]) -> tuple[dict[str, Product], dict[str, Product]]:
    numeric_ids = []
    sku_values = []
    for item in raw_items:
        raw_item_id = str(item.get("item_id") or "").strip()
        if not raw_item_id:
            continue
        if raw_item_id.isdigit():
            numeric_ids.append(int(raw_item_id))
        else:
            sku_values.append(raw_item_id)
    products_by_id = {str(product.id): product for product in Product.objects.filter(id__in=numeric_ids)}
    products_by_sku = {product.sku: product for product in Product.objects.filter(sku__in=sku_values)}
    return products_by_id, products_by_sku


def _resolve_product(raw_item_id: str, *, products_by_id=None, products_by_sku=None):
    item_id = str(raw_item_id or "").strip()
    if not item_id:
        return None
    if products_by_id is not None or products_by_sku is not None:
        if item_id.isdigit():
            return (products_by_id or {}).get(item_id)
        return (products_by_sku or {}).get(item_id)
    if item_id.isdigit():
        return Product.objects.filter(pk=int(item_id)).first()
    return Product.objects.filter(sku=item_id).first()


def _stage1_event_meta(payload: dict, item: dict | None = None) -> dict[str, object]:
    item = item or {}
    return {
        "recommendation_id": str(payload.get("recommendation_id") or item.get("recommendation_id") or ""),
        "impression_id": str(item.get("impression_id") or payload.get("impression_id") or ""),
        "engine_source": str(payload.get("engine_source") or ""),
        "service_source": str(payload.get("service_source") or ""),
        "fallback_source": str(payload.get("fallback_source") or ""),
        "empty_reason": str(payload.get("empty_reason") or ""),
        "latency_ms": _safe_int(payload.get("latency_ms") or 0),
    }


class AnalyticsIngestView(View):
    """Common safety rails for storefront analytics ingest endpoints."""

    throttle_scope = "feedback"

    def dispatch(self, request, *args, **kwargs):
        if request.method.lower() == "post":
            if not _same_origin_or_allowed_host(request):
                return JsonResponse({"ok": False, "error": "invalid_origin"}, status=403)
            if _ingest_throttled(request, scope=self.throttle_scope):
                return JsonResponse({"ok": False, "error": "rate_limited"}, status=429)
        return super().dispatch(request, *args, **kwargs)


class SearchFeedbackIngestView(AnalyticsIngestView):
    """Accept same-origin search feedback events from the storefront runtime."""

    allowed_events = {"search", "search_result_click"}
    throttle_scope = "search-feedback"

    @log_calls(log)
    def post(self, request):
        payload, error_response = _parse_json_payload(request)
        if error_response is not None:
            return error_response

        event_name = str(payload.get("event") or "").strip()
        if event_name not in self.allowed_events:
            return JsonResponse({"ok": False, "error": "unsupported_event"}, status=400)

        observe_search_feedback_event(
            event_name=event_name,
            surface=str(payload.get("page_type") or payload.get("ui_surface") or "unknown"),
            origin=str(payload.get("search_origin") or payload.get("item_list_name") or "unknown"),
            search_term=str(payload.get("search_term") or ""),
            item_id=str(payload.get("item_id") or ""),
            item_name=str(payload.get("item_name") or ""),
            position=_safe_int(payload.get("position") or 0),
            results_count=_safe_int(payload.get("results_count") or 0),
            provider=str(payload.get("search_provider") or payload.get("provider") or ""),
            rewrite_kind=str(payload.get("search_rewrite_kind") or payload.get("rewrite_kind") or ""),
            logger=log,
        )
        remember_search_feedback(request, payload)
        return HttpResponse(status=204)


class RecommendationFeedbackIngestView(AnalyticsIngestView):
    """Accept same-origin recommendation feedback events from the storefront runtime."""

    allowed_events = {
        "recommendation_impression",
        "recommendation_click",
        "add_to_cart",
        "remove_from_cart",
        "purchase",
        "recommendation_dismiss",
        "favorite_add",
        "saved_list_add",
    }
    throttle_scope = "recommendation-feedback"

    @log_calls(log)
    def post(self, request):
        payload, error_response = _parse_json_payload(request)
        if error_response is not None:
            return error_response

        event_name = str(payload.get("event") or "").strip()
        if event_name not in self.allowed_events:
            return JsonResponse({"ok": False, "error": "unsupported_event"}, status=400)

        product = None
        if event_name == "recommendation_impression":
            items = ((payload.get("ecommerce") or {}).get("items") or [])[:12]
            products_by_id, products_by_sku = _product_lookup_maps(items)
            normalized_items = []
            for position, item in enumerate(items, start=1):
                item_id = str(item.get("item_id") or "").strip()
                product = _resolve_product(item_id, products_by_id=products_by_id, products_by_sku=products_by_sku)
                if not product:
                    continue
                stage1_meta = _stage1_event_meta(payload, item)
                normalized_items.append(
                    {
                        "item_id": str(product.id),
                        "item_name": str(item.get("item_name") or product.name),
                        "recommendation_id": str(stage1_meta["recommendation_id"] or ""),
                        "impression_id": str(stage1_meta["impression_id"] or ""),
                    }
                )
                RecommendationEvent.objects.create(
                    event="recommendation_impression",
                    user=request.user if getattr(request.user, "is_authenticated", False) else None,
                    session_key=request.session.session_key or "",
                    surface=str(payload.get("surface") or payload.get("page_type") or "unknown"),
                    recommendation_source=str(payload.get("recommendation_source") or "unknown"),
                    product=product,
                    seller_id=product.seller_id,
                    brand_id=product.brand_id,
                    category_id=product.category_id,
                    position=position,
                    request_id=str(payload.get("request_id") or ""),
                    payload={
                        "experiment_variant": str(payload.get("experiment_variant") or "control"),
                        "strategy": str(payload.get("strategy") or ""),
                        "model_version": str(payload.get("model_version") or ""),
                        **stage1_meta,
                        "recommendation_reason_codes": [str(value) for value in (item.get("recommendation_reason_codes") or []) if str(value).strip()],
                        "recommendation_candidate_sources": [str(value) for value in (item.get("recommendation_candidate_sources") or []) if str(value).strip()],
                        "recommendation_score_hint": float(item.get("recommendation_score_hint") or 0),
                    },
                )
                observe_recommendation_event(
                    event_name="recommendation_impression",
                    surface=str(payload.get("surface") or payload.get("page_type") or "unknown"),
                    source=str(payload.get("recommendation_source") or "unknown"),
                    variant=str(payload.get("experiment_variant") or "control"),
                    product_id=product.id,
                    position=position,
                    request_id=str(payload.get("request_id") or ""),
                    logger=log,
                )
            if normalized_items:
                remember_recommendation_feedback(
                    request,
                    {
                        **payload,
                        "ecommerce": {"items": normalized_items},
                    },
                )
            return HttpResponse(status=204)

        item_id = str(payload.get("item_id") or "").strip()
        product = _resolve_product(item_id)
        if product is not None:
            remember_recommendation_feedback(request, {**payload, "item_id": str(product.id)})
            record_recommendation_event(
                request=request,
                event_name=event_name,
                product=product,
                payload=payload,
                logger=log,
            )
        return HttpResponse(status=204)
