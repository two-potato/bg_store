from __future__ import annotations

from django import template

from shopfront.request_state import favorite_product_ids_for_user, session_cart_state

register = template.Library()


def _request_cart_qty_map(request) -> dict[int, int]:
    """Internal helper for request cart qty map."""
    cached = getattr(request, "_shopfront_cart_qty_map", None)
    if cached is not None:
        return cached
    _, qty_map, _, _ = session_cart_state(request.session.get("cart", {}) or {})
    request._shopfront_cart_qty_map = qty_map
    return qty_map


def _request_favorite_ids(request) -> set[int]:
    """Internal helper for request favorite ids."""
    cached = getattr(request, "_shopfront_favorite_ids", None)
    if cached is not None:
        return cached
    favorite_ids = set(favorite_product_ids_for_user(getattr(request, "user", None), limit=2000))
    request._shopfront_favorite_ids = favorite_ids
    return favorite_ids


@register.simple_tag
def cart_quantity(request, product_id: int) -> int:
    """Handle cart quantity."""
    try:
        pid = int(product_id)
    except (TypeError, ValueError):
        return 0
    return int(_request_cart_qty_map(request).get(pid, 0))


@register.simple_tag
def product_in_cart(request, product_id: int) -> bool:
    """Handle product in cart."""
    return bool(cart_quantity(request, product_id))


@register.simple_tag
def product_favorited(request, product_id: int) -> bool:
    """Handle product favorited."""
    if not getattr(getattr(request, "user", None), "is_authenticated", False):
        return False
    try:
        pid = int(product_id)
    except (TypeError, ValueError):
        return False
    return pid in _request_favorite_ids(request)
