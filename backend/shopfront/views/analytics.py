"""Analytics ingest views for first-party storefront feedback signals."""

from __future__ import annotations

import json

from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from core.logging_utils import log_calls

from catalog.models import Product

from ..models import RecommendationEvent
from ..recommendation_attribution_service import (
    record_recommendation_event,
    remember_recommendation_feedback,
)
from ..recommendation_observability import observe_recommendation_event
from ..search_attribution_service import remember_search_feedback
from ..search_observability import observe_search_feedback_event
from . import log


@method_decorator(csrf_exempt, name="dispatch")
class SearchFeedbackIngestView(View):
    """Accept same-origin search feedback events from the storefront runtime."""

    allowed_events = {"search", "search_result_click"}

    @log_calls(log)
    def post(self, request):
        try:
            payload = json.loads((request.body or b"{}").decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)

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
            position=int(payload.get("position") or 0),
            results_count=int(payload.get("results_count") or 0),
            provider=str(payload.get("search_provider") or payload.get("provider") or ""),
            rewrite_kind=str(payload.get("search_rewrite_kind") or payload.get("rewrite_kind") or ""),
            logger=log,
        )
        remember_search_feedback(request, payload)
        return HttpResponse(status=204)


@method_decorator(csrf_exempt, name="dispatch")
class RecommendationFeedbackIngestView(View):
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

    @log_calls(log)
    def post(self, request):
        try:
            payload = json.loads((request.body or b"{}").decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)

        event_name = str(payload.get("event") or "").strip()
        if event_name not in self.allowed_events:
            return JsonResponse({"ok": False, "error": "unsupported_event"}, status=400)

        product = None
        item_id = ""
        if event_name == "recommendation_impression":
            items = ((payload.get("ecommerce") or {}).get("items") or [])[:12]
            normalized_items = []
            for position, item in enumerate(items, start=1):
                item_id = str(item.get("item_id") or "").strip()
                product = Product.objects.filter(pk=int(item_id)).first() if item_id.isdigit() else Product.objects.filter(sku=item_id).first()
                if not product:
                    continue
                normalized_items.append({"item_id": str(product.id), "item_name": str(item.get("item_name") or product.name)})
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
        product = Product.objects.filter(pk=int(item_id)).first() if item_id.isdigit() else Product.objects.filter(sku=item_id).first()
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
