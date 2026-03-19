"""Session-backed search attribution helpers for storefront feedback loops."""

from __future__ import annotations

import time

from orders.models import Order


SEARCH_ATTRIBUTION_SESSION_KEY = "shopfront_search_attribution_v1"
SEARCH_ATTRIBUTION_TTL_SECONDS = 60 * 60 * 6


def _now_ts() -> int:
    return int(time.time())


def _ensure_state(request) -> dict:
    state = request.session.get(SEARCH_ATTRIBUTION_SESSION_KEY)
    if not isinstance(state, dict):
        state = {}
    state.setdefault("latest_search", {})
    state.setdefault("impressions", {})
    state.setdefault("clicks", {})
    state.setdefault("cart_items", {})
    state.setdefault("orders", {})
    return state


def _is_fresh(entry: dict, *, now_ts: int | None = None) -> bool:
    now_value = _now_ts() if now_ts is None else now_ts
    try:
        ts = int(entry.get("ts") or 0)
    except (TypeError, ValueError):
        return False
    return ts > 0 and (now_value - ts) <= SEARCH_ATTRIBUTION_TTL_SECONDS


def _base_attribution(payload: dict, *, event_name: str) -> dict:
    return {
        "event": event_name,
        "search_term": str(payload.get("search_term") or ""),
        "search_origin": str(payload.get("search_origin") or payload.get("item_list_name") or "unknown"),
        "search_provider": str(payload.get("search_provider") or payload.get("provider") or ""),
        "search_rewrite_kind": str(payload.get("search_rewrite_kind") or payload.get("rewrite_kind") or ""),
        "results_count": int(payload.get("results_count") or 0),
        "page_type": str(payload.get("page_type") or payload.get("ui_surface") or "unknown"),
        "ts": _now_ts(),
    }


def remember_search_feedback(request, payload: dict) -> None:
    """Persist lightweight search impression/click context in the session."""
    event_name = str(payload.get("event") or "").strip()
    if event_name not in {"search", "search_result_click"}:
        return
    state = _ensure_state(request)
    base = _base_attribution(payload, event_name=event_name)
    if event_name == "search":
        state["latest_search"] = base
        impressions = {}
        for position, item in enumerate(((payload.get("ecommerce") or {}).get("items") or []), start=1):
            product_id = str(item.get("item_id") or "").strip()
            if not product_id:
                continue
            entry = dict(base)
            entry["item_id"] = product_id
            entry["item_name"] = str(item.get("item_name") or "")
            entry["position"] = position
            impressions[product_id] = entry
        state["impressions"] = impressions
    else:
        product_id = str(payload.get("item_id") or "").strip()
        if product_id:
            entry = dict(base)
            entry["item_id"] = product_id
            entry["item_name"] = str(payload.get("item_name") or "")
            entry["position"] = int(payload.get("position") or 0)
            state["clicks"][product_id] = entry
    request.session[SEARCH_ATTRIBUTION_SESSION_KEY] = state
    request.session.modified = True


def search_attribution_for_product(request, product_id: int) -> dict:
    """Return the freshest attribution candidate for a given product id."""
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


def bind_cart_item_search_attribution(request, *, product_id: int, attribution: dict) -> None:
    """Attach search attribution to a cart item for later checkout/purchase linkage."""
    if not attribution:
        return
    state = _ensure_state(request)
    cart_items = state.setdefault("cart_items", {})
    cart_items[str(product_id)] = dict(attribution)
    request.session[SEARCH_ATTRIBUTION_SESSION_KEY] = state
    request.session.modified = True


def remove_cart_item_search_attribution(request, *, product_id: str | int) -> None:
    state = _ensure_state(request)
    state.setdefault("cart_items", {}).pop(str(product_id), None)
    request.session[SEARCH_ATTRIBUTION_SESSION_KEY] = state
    request.session.modified = True


def clear_cart_search_attribution(request) -> None:
    state = _ensure_state(request)
    state["cart_items"] = {}
    request.session[SEARCH_ATTRIBUTION_SESSION_KEY] = state
    request.session.modified = True


def remember_order_search_attribution(request, *, order: Order, attribution: dict) -> None:
    """Persist order-level attribution after cart-to-order conversion."""
    if not attribution:
        return
    state = _ensure_state(request)
    state.setdefault("orders", {})[str(order.id)] = {"ts": _now_ts(), "payload": dict(attribution)}
    request.session[SEARCH_ATTRIBUTION_SESSION_KEY] = state
    request.session.modified = True


def order_search_attribution(request, order: Order) -> dict:
    """Aggregate cart-level search attribution for a completed order."""
    state = _ensure_state(request)
    archived = (state.get("orders", {}) or {}).get(str(order.id)) or {}
    if archived and _is_fresh(archived):
        payload = archived.get("payload")
        if isinstance(payload, dict):
            return dict(payload)
    cart_items = state.get("cart_items", {}) or {}
    item_entries = []
    search_terms = []
    for item in order.items.select_related("product").all():
        entry = cart_items.get(str(item.product_id))
        if not entry or not _is_fresh(entry):
            continue
        item_entries.append(
            {
                "product_id": str(item.product_id),
                "product_name": item.name,
                "qty": int(item.qty or 0),
                "search_term": entry.get("search_term", ""),
                "search_origin": entry.get("search_origin", ""),
                "search_provider": entry.get("search_provider", ""),
                "search_rewrite_kind": entry.get("search_rewrite_kind", ""),
                "position": int(entry.get("position") or 0),
            }
        )
        term = str(entry.get("search_term") or "").strip()
        if term and term not in search_terms:
            search_terms.append(term)
    if not item_entries:
        return {}
    return {
        "attributed_item_count": len(item_entries),
        "attributed_queries": search_terms[:8],
        "items": item_entries[:24],
    }
