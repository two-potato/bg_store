"""Checkout attribution state owned by the commerce domain.

Search and recommendation services are stateless execution engines. Linking a
browser session/cart to an order is transactional Django state, so it belongs
here rather than in either service implementation.
"""

from __future__ import annotations

import time

from orders.models import Order

SEARCH_ATTRIBUTION_SESSION_KEY = "shopfront_search_attribution_v1"
RECOMMENDATION_ATTRIBUTION_SESSION_KEY = "shopfront_recommendation_attribution_v1"
SEARCH_ATTRIBUTION_TTL_SECONDS = 60 * 60 * 6
RECOMMENDATION_ATTRIBUTION_TTL_SECONDS = 60 * 60 * 24


def _now_ts() -> int:
    return int(time.time())


def _state(request, key: str) -> dict:
    value = request.session.get(key)
    state = dict(value) if isinstance(value, dict) else {}
    state.setdefault("orders", {})
    state.setdefault("cart_items", {})
    return state


def _fresh(entry: dict, ttl: int) -> bool:
    try:
        ts = int(entry.get("ts") or 0)
    except (TypeError, ValueError):
        return False
    return ts > 0 and (_now_ts() - ts) <= ttl


def _remember_order(request, *, key: str, order: Order, attribution: dict) -> None:
    if not attribution:
        return
    state = _state(request, key)
    state["orders"][str(order.id)] = {"ts": _now_ts(), "payload": dict(attribution)}
    request.session[key] = state
    request.session.modified = True


def remember_order_search_attribution(request, *, order: Order, attribution: dict) -> None:
    _remember_order(request, key=SEARCH_ATTRIBUTION_SESSION_KEY, order=order, attribution=attribution)


def remember_order_recommendation_attribution(request, *, order: Order, attribution: dict) -> None:
    _remember_order(request, key=RECOMMENDATION_ATTRIBUTION_SESSION_KEY, order=order, attribution=attribution)


def order_search_attribution(request, order: Order) -> dict:
    state = _state(request, SEARCH_ATTRIBUTION_SESSION_KEY)
    archived = state["orders"].get(str(order.id)) or {}
    if archived and _fresh(archived, SEARCH_ATTRIBUTION_TTL_SECONDS):
        payload = archived.get("payload")
        if isinstance(payload, dict):
            return dict(payload)
    entries = []
    terms: list[str] = []
    for item in order.items.select_related("product").all():
        entry = state["cart_items"].get(str(item.product_id)) or {}
        if not entry or not _fresh(entry, SEARCH_ATTRIBUTION_TTL_SECONDS):
            continue
        entries.append({
            "product_id": str(item.product_id),
            "product_name": item.name,
            "qty": int(item.qty or 0),
            "search_term": entry.get("search_term", ""),
            "search_origin": entry.get("search_origin", ""),
            "search_provider": entry.get("search_provider", ""),
            "search_rewrite_kind": entry.get("search_rewrite_kind", ""),
            "position": int(entry.get("position") or 0),
        })
        term = str(entry.get("search_term") or "").strip()
        if term and term not in terms:
            terms.append(term)
    if not entries:
        return {}
    return {"attributed_item_count": len(entries), "attributed_queries": terms[:8], "items": entries[:24]}


def order_recommendation_attribution(request, order: Order) -> dict:
    state = _state(request, RECOMMENDATION_ATTRIBUTION_SESSION_KEY)
    archived = state["orders"].get(str(order.id)) or {}
    if archived and _fresh(archived, RECOMMENDATION_ATTRIBUTION_TTL_SECONDS):
        payload = archived.get("payload")
        if isinstance(payload, dict):
            return dict(payload)
    entries = []
    for item in order.items.select_related("product").all():
        entry = state["cart_items"].get(str(item.product_id)) or {}
        if not entry or not _fresh(entry, RECOMMENDATION_ATTRIBUTION_TTL_SECONDS):
            continue
        entries.append({
            "product_id": str(item.product_id),
            "product_name": item.name,
            "qty": int(item.qty or 0),
            "recommendation_source": entry.get("recommendation_source", ""),
            "recommendation_id": entry.get("recommendation_id", ""),
            "impression_id": entry.get("impression_id", ""),
            "surface": entry.get("surface", ""),
            "experiment_variant": entry.get("experiment_variant", "control"),
            "strategy": entry.get("strategy", ""),
            "model_version": entry.get("model_version", ""),
            "engine_source": entry.get("engine_source", ""),
            "service_source": entry.get("service_source", ""),
            "fallback_source": entry.get("fallback_source", ""),
            "empty_reason": entry.get("empty_reason", ""),
            "latency_ms": int(entry.get("latency_ms") or 0),
            "request_id": entry.get("request_id", ""),
            "position": int(entry.get("position") or 0),
            "reason_codes": list(entry.get("reason_codes") or []),
            "candidate_sources": list(entry.get("candidate_sources") or []),
            "score_hint": float(entry.get("score_hint") or 0),
        })
    if not entries:
        return {}
    return {
        "attributed_item_count": len(entries),
        "sources": sorted({str(item.get("recommendation_source") or "unknown") for item in entries}),
        "items": entries[:24],
    }
