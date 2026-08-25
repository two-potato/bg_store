from __future__ import annotations

SEARCH_ATTRIBUTION_SESSION_KEY = "shopfront_search_attribution_v1"
RECOMMENDATION_ATTRIBUTION_SESSION_KEY = "shopfront_recommendation_attribution_v1"


def _state(request, key: str) -> dict:
    value = request.session.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _remove_cart_item(request, *, key: str, product_id: str | int) -> None:
    state = _state(request, key)
    cart_items = state.get("cart_items")
    if not isinstance(cart_items, dict):
        cart_items = {}
    else:
        cart_items = dict(cart_items)
    cart_items.pop(str(product_id), None)
    state["cart_items"] = cart_items
    request.session[key] = state
    request.session.modified = True


def _clear_cart(request, *, key: str) -> None:
    state = _state(request, key)
    state["cart_items"] = {}
    request.session[key] = state
    request.session.modified = True


def remove_cart_item_search_attribution(request, *, product_id: str | int) -> None:
    _remove_cart_item(request, key=SEARCH_ATTRIBUTION_SESSION_KEY, product_id=product_id)


def clear_cart_search_attribution(request) -> None:
    _clear_cart(request, key=SEARCH_ATTRIBUTION_SESSION_KEY)


def remove_cart_item_recommendation_attribution(request, *, product_id: str | int) -> None:
    _remove_cart_item(request, key=RECOMMENDATION_ATTRIBUTION_SESSION_KEY, product_id=product_id)


def clear_cart_recommendation_attribution(request) -> None:
    _clear_cart(request, key=RECOMMENDATION_ATTRIBUTION_SESSION_KEY)
