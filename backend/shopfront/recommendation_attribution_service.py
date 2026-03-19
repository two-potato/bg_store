"""Session-backed recommendation attribution helpers."""

from __future__ import annotations

import time

from orders.models import Order

from .models import RecommendationEvent
from .recommendation_observability import observe_recommendation_event
from .recommendation_policy import remember_recommendation_dismiss


RECOMMENDATION_ATTRIBUTION_SESSION_KEY = "shopfront_recommendation_attribution_v1"
RECOMMENDATION_ATTRIBUTION_TTL_SECONDS = 60 * 60 * 24


def _now_ts() -> int:
    return int(time.time())


def _ensure_state(request) -> dict:
    state = request.session.get(RECOMMENDATION_ATTRIBUTION_SESSION_KEY)
    if not isinstance(state, dict):
        state = {}
    state.setdefault("impressions", {})
    state.setdefault("clicks", {})
    state.setdefault("cart_items", {})
    state.setdefault("orders", {})
    return state


def _is_fresh(entry: dict, *, now_ts: int | None = None) -> bool:
    current_ts = _now_ts() if now_ts is None else now_ts
    try:
        ts = int(entry.get("ts") or 0)
    except (TypeError, ValueError):
        return False
    return ts > 0 and (current_ts - ts) <= RECOMMENDATION_ATTRIBUTION_TTL_SECONDS


def _base_entry(payload: dict, *, event_name: str) -> dict:
    return {
        "event": event_name,
        "recommendation_source": str(payload.get("recommendation_source") or payload.get("item_list_name") or "unknown"),
        "surface": str(payload.get("surface") or payload.get("page_type") or payload.get("ui_surface") or "unknown"),
        "request_id": str(payload.get("request_id") or ""),
        "experiment_variant": str(payload.get("experiment_variant") or "control"),
        "strategy": str(payload.get("strategy") or ""),
        "model_version": str(payload.get("model_version") or ""),
        "ts": _now_ts(),
    }


def remember_recommendation_feedback(request, payload: dict) -> None:
    event_name = str(payload.get("event") or "").strip()
    if event_name == "recommendation_dismiss":
        product_id = str(payload.get("item_id") or "").strip()
        if product_id.isdigit():
            remember_recommendation_dismiss(
                request,
                surface=str(payload.get("surface") or payload.get("page_type") or "unknown"),
                product_id=int(product_id),
            )
        return
    if event_name not in {"recommendation_impression", "recommendation_click"}:
        return
    state = _ensure_state(request)
    base = _base_entry(payload, event_name=event_name)
    if event_name == "recommendation_impression":
        for position, item in enumerate(((payload.get("ecommerce") or {}).get("items") or []), start=1):
            product_id = str(item.get("item_id") or "").strip()
            if not product_id:
                continue
            entry = dict(base)
            entry["item_id"] = product_id
            entry["item_name"] = str(item.get("item_name") or "")
            entry["position"] = position
            entry["reason_codes"] = [str(value) for value in (item.get("recommendation_reason_codes") or []) if str(value).strip()]
            entry["candidate_sources"] = [str(value) for value in (item.get("recommendation_candidate_sources") or []) if str(value).strip()]
            entry["score_hint"] = float(item.get("recommendation_score_hint") or 0)
            state["impressions"][product_id] = entry
    else:
        product_id = str(payload.get("item_id") or "").strip()
        if product_id:
            entry = dict(base)
            entry["item_id"] = product_id
            entry["item_name"] = str(payload.get("item_name") or "")
            entry["position"] = int(payload.get("position") or 0)
            entry["reason_codes"] = [str(value) for value in (payload.get("recommendation_reason_codes") or []) if str(value).strip()]
            entry["candidate_sources"] = [str(value) for value in (payload.get("recommendation_candidate_sources") or []) if str(value).strip()]
            entry["score_hint"] = float(payload.get("recommendation_score_hint") or 0)
            state["clicks"][product_id] = entry
    request.session[RECOMMENDATION_ATTRIBUTION_SESSION_KEY] = state
    request.session.modified = True


def recommendation_attribution_for_product(request, product_id: int) -> dict:
    state = _ensure_state(request)
    now_ts = _now_ts()
    product_key = str(product_id)
    click = state.get("clicks", {}).get(product_key) or {}
    if click and _is_fresh(click, now_ts=now_ts):
        return dict(click)
    impression = state.get("impressions", {}).get(product_key) or {}
    if impression and _is_fresh(impression, now_ts=now_ts):
        return dict(impression)
    return {}


def bind_cart_item_recommendation_attribution(request, *, product_id: int, attribution: dict) -> None:
    if not attribution:
        return
    state = _ensure_state(request)
    state.setdefault("cart_items", {})[str(product_id)] = dict(attribution)
    request.session[RECOMMENDATION_ATTRIBUTION_SESSION_KEY] = state
    request.session.modified = True


def cart_item_recommendation_attribution(request, *, product_id: str | int) -> dict:
    state = _ensure_state(request)
    entry = (state.get("cart_items", {}) or {}).get(str(product_id)) or {}
    if entry and _is_fresh(entry):
        return dict(entry)
    return {}


def remove_cart_item_recommendation_attribution(request, *, product_id: str | int) -> None:
    state = _ensure_state(request)
    state.setdefault("cart_items", {}).pop(str(product_id), None)
    request.session[RECOMMENDATION_ATTRIBUTION_SESSION_KEY] = state
    request.session.modified = True


def clear_cart_recommendation_attribution(request) -> None:
    state = _ensure_state(request)
    state["cart_items"] = {}
    request.session[RECOMMENDATION_ATTRIBUTION_SESSION_KEY] = state
    request.session.modified = True


def remember_order_recommendation_attribution(request, *, order: Order, attribution: dict) -> None:
    if not attribution:
        return
    state = _ensure_state(request)
    state.setdefault("orders", {})[str(order.id)] = {"ts": _now_ts(), "payload": dict(attribution)}
    request.session[RECOMMENDATION_ATTRIBUTION_SESSION_KEY] = state
    request.session.modified = True


def order_recommendation_attribution(request, order: Order) -> dict:
    state = _ensure_state(request)
    archived = (state.get("orders", {}) or {}).get(str(order.id)) or {}
    if archived and _is_fresh(archived):
        payload = archived.get("payload")
        if isinstance(payload, dict):
            return dict(payload)
    cart_items = state.get("cart_items", {}) or {}
    item_entries = []
    for item in order.items.select_related("product").all():
        entry = cart_items.get(str(item.product_id))
        if not entry or not _is_fresh(entry):
            continue
        item_entries.append(
            {
                "product_id": str(item.product_id),
                "product_name": item.name,
                "qty": int(item.qty or 0),
                "recommendation_source": entry.get("recommendation_source", ""),
                "surface": entry.get("surface", ""),
                "experiment_variant": entry.get("experiment_variant", "control"),
                "strategy": entry.get("strategy", ""),
                "model_version": entry.get("model_version", ""),
                "request_id": entry.get("request_id", ""),
                "position": int(entry.get("position") or 0),
                "reason_codes": list(entry.get("reason_codes") or []),
                "candidate_sources": list(entry.get("candidate_sources") or []),
                "score_hint": float(entry.get("score_hint") or 0),
            }
        )
    if not item_entries:
        return {}
    return {
        "attributed_item_count": len(item_entries),
        "sources": sorted({str(item.get("recommendation_source") or "unknown") for item in item_entries}),
        "items": item_entries[:24],
    }


def record_recommendation_event(
    *,
    request,
    event_name: str,
    product,
    attribution: dict | None = None,
    payload: dict | None = None,
    logger,
):
    product_id = getattr(product, "id", None)
    attr = dict(attribution or {})
    payload = dict(payload or {})
    if not attr and product_id:
        attr = recommendation_attribution_for_product(request, int(product_id))
    surface = str(attr.get("surface") or payload.get("surface") or "")
    source = str(attr.get("recommendation_source") or payload.get("recommendation_source") or "")
    request_id = str(attr.get("request_id") or payload.get("request_id") or "")
    experiment_variant = str(attr.get("experiment_variant") or payload.get("experiment_variant") or "control")
    strategy = str(attr.get("strategy") or payload.get("strategy") or "")
    model_version = str(attr.get("model_version") or payload.get("model_version") or "")
    reason_codes = [str(value) for value in (attr.get("reason_codes") or payload.get("recommendation_reason_codes") or []) if str(value).strip()]
    candidate_sources = [str(value) for value in (attr.get("candidate_sources") or payload.get("recommendation_candidate_sources") or []) if str(value).strip()]
    row = RecommendationEvent.objects.create(
        event=event_name,
        user=request.user if getattr(request.user, "is_authenticated", False) else None,
        session_key=request.session.session_key or "",
        surface=surface,
        recommendation_source=source,
        product=product,
        seller_id=getattr(product, "seller_id", None),
        brand_id=getattr(product, "brand_id", None),
        category_id=getattr(product, "category_id", None),
        position=int(attr.get("position") or 0),
        request_id=request_id,
        payload={
            **payload,
            "experiment_variant": experiment_variant,
            "strategy": strategy,
            "model_version": model_version,
            "recommendation_reason_codes": reason_codes,
            "recommendation_candidate_sources": candidate_sources,
            "recommendation_score_hint": float(attr.get("score_hint") or payload.get("recommendation_score_hint") or 0),
        },
    )
    observe_recommendation_event(
        event_name=event_name,
        surface=row.surface,
        source=row.recommendation_source,
        variant=str((row.payload or {}).get("experiment_variant") or "control"),
        product_id=product_id,
        position=row.position,
        request_id=row.request_id,
        logger=logger,
    )
    return row
