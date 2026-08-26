"""Order-owned background jobs for checkout attribution feedback."""

import logging

from celery import shared_task

from legacy_shopfront_state.models import RecommendationEvent
from orders.models import Order
from recommendation_api.observability import observe_recommendation_order_attribution
from search_api.observability import observe_search_feedback_event, observe_search_order_attribution

log = logging.getLogger("orders.attribution")


@shared_task
def emit_checkout_search_feedback(*, order_id: int, attribution: dict) -> int:
    if not attribution:
        return 0
    order = Order.objects.filter(id=order_id).first()
    if order is None:
        return 0
    observe_search_order_attribution(order=order, attribution=attribution, logger=log)
    emitted = 0
    for item in attribution.get("items", []):
        observe_search_feedback_event(
            event_name="purchase",
            surface="checkout",
            origin=item.get("search_origin", "unknown"),
            search_term=item.get("search_term", ""),
            item_id=item.get("product_id", ""),
            item_name=item.get("product_name", ""),
            position=int(item.get("position") or 0),
            results_count=0,
            provider=item.get("search_provider", ""),
            rewrite_kind=item.get("search_rewrite_kind", ""),
            logger=log,
        )
        emitted += 1
    return emitted


@shared_task
def emit_checkout_recommendation_feedback(*, order_id: int, attribution: dict) -> int:
    if not attribution:
        return 0
    order = Order.objects.filter(id=order_id).first()
    if order is None:
        return 0
    observe_recommendation_order_attribution(order=order, attribution=attribution, logger=log)
    order_items = list(order.items.select_related("product"))
    product_by_id = {str(item.product_id): item.product for item in order_items}
    emitted = 0
    for item in attribution.get("items", []):
        product = product_by_id.get(str(item.get("product_id")))
        if product is None:
            continue
        RecommendationEvent.objects.create(
            event="purchase",
            user=order.placed_by if order.placed_by_id else None,
            session_key="",
            surface=str(item.get("surface") or "checkout"),
            recommendation_source=str(item.get("recommendation_source") or ""),
            product=product,
            seller_id=getattr(product, "seller_id", None),
            brand_id=getattr(product, "brand_id", None),
            category_id=getattr(product, "category_id", None),
            position=int(item.get("position") or 0),
            request_id=str(item.get("request_id") or ""),
            payload={
                "surface": "checkout",
                "order_id": order.id,
                "qty": int(item.get("qty") or 0),
                "reason_codes": list(item.get("reason_codes") or []),
                "candidate_sources": list(item.get("candidate_sources") or []),
                "score_hint": float(item.get("score_hint") or 0),
            },
        )
        emitted += 1
    return emitted
