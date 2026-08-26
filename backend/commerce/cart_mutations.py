from __future__ import annotations

from decimal import Decimal

from django.db.models import Prefetch

from catalog.models import Product
from catalog.offer_service import active_offer_queryset, apply_offer_snapshot

from .cart_attribution import (
    clear_cart_recommendation_attribution,
    clear_cart_search_attribution,
    remove_cart_item_recommendation_attribution,
    remove_cart_item_search_attribution,
)
from .cart_store import persist_cart_for_user


def _load_cart_product(product_id: int):
    """Load a product with the active offer snapshot required by cart operations."""
    product = Product.objects.prefetch_related(
        Prefetch("seller_offers", queryset=active_offer_queryset())
    ).get(pk=product_id)
    apply_offer_snapshot([product])
    return product


def _max_qty_for_product(product) -> int:
    """Return the maximum quantity currently available for the product."""
    return max(0, int(product.display_stock_qty or 0))


def add_to_cart_session(*, request, product_id: int, qty: int, logger):
    """Add a product to the session cart and persist the resulting cart state."""
    cart = request.session.setdefault("cart", {})
    product = _load_cart_product(product_id)
    max_qty = _max_qty_for_product(product)
    current = int(cart.get(str(product_id), {"qty": 0}).get("qty", 0))
    new_qty = current + max(1, qty)
    if max_qty > 0 and new_qty > max_qty:
        logger.info(
            "cart_qty_capped_by_stock",
            extra={"product_id": product_id, "requested": new_qty, "stock": max_qty},
        )
        new_qty = max_qty
    if new_qty <= 0:
        cart.pop(str(product_id), None)
    else:
        cart[str(product_id)] = {"qty": new_qty}
    request.session.modified = True
    persist_cart_for_user(request.user, request.session.get("cart", {}))
    current_qty = cart.get(str(product_id), {}).get("qty", 0)
    line_value = (
        Decimal(str(product.display_price)) * Decimal(max(1, qty))
    ).quantize(Decimal("0.01"))
    return {
        "product": product,
        "current_qty": current_qty,
        "line_value": line_value,
    }


def remove_from_cart_session(*, request, product_id: str | int):
    """Remove a product from the cart and clear its search/recommendation attribution."""
    cart = request.session.setdefault("cart", {})
    cart.pop(str(product_id), None)
    remove_cart_item_search_attribution(request, product_id=product_id)
    remove_cart_item_recommendation_attribution(request, product_id=product_id)
    request.session.modified = True
    persist_cart_for_user(request.user, request.session.get("cart", {}))


def clear_cart_session(*, request):
    """Clear the cart and all cart-level search/recommendation attribution."""
    request.session["cart"] = {}
    clear_cart_search_attribution(request)
    clear_cart_recommendation_attribution(request)
    request.session.modified = True
    persist_cart_for_user(request.user, request.session.get("cart", {}))


def update_cart_session(*, request, product_id: int, op: str, requested_qty, logger):
    """Update a cart line quantity and persist the resulting cart state."""
    cart = request.session.setdefault("cart", {})
    item = cart.get(str(product_id))
    if not item:
        return {"missing": True, "qty": 0, "product": None}

    qty = int(item.get("qty", 1))
    if op == "inc":
        qty += 1
    elif op == "dec":
        qty = max(1, qty - 1)
    elif op == "set":
        try:
            qty = max(1, int(requested_qty or 1))
        except (TypeError, ValueError):
            pass

    try:
        product = _load_cart_product(product_id)
        max_qty = _max_qty_for_product(product)
    except Product.DoesNotExist:
        logger.warning("cart_update_product_not_found", extra={"product_id": product_id})
        product = None
        max_qty = 0

    if max_qty > 0 and qty > max_qty:
        logger.info(
            "cart_qty_capped_by_stock",
            extra={"product_id": product_id, "requested": qty, "stock": max_qty},
        )
        qty = max_qty
    if qty <= 0:
        cart.pop(str(product_id), None)
        qty = 0
    else:
        item["qty"] = qty
        cart[str(product_id)] = item
    request.session.modified = True
    persist_cart_for_user(request.user, request.session.get("cart", {}))
    return {"missing": False, "qty": qty, "product": product}
