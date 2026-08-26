"""Checkout rendering helpers used by cart and checkout views."""

from __future__ import annotations

from django.shortcuts import render

from ..checkout_common import (
    attach_cart_badge_oob as _shared_attach_cart_badge_oob,
    build_checkout_context as _shared_checkout_context,
)
from ..checkout_support import tracking_item_from_product as _tracking_item_from_product
from .utils_catalog import _new_idempotency_key


def _checkout_context(
    req,
    form_data=None,
    checkout_error=None,
    *,
    tracking_item_from_product=_tracking_item_from_product,
):
    """Build checkout page context with legacy idempotency behavior."""
    return _shared_checkout_context(
        req,
        form_data=form_data,
        checkout_error=checkout_error or "",
        idempotency_key_factory=_new_idempotency_key,
        tracking_item_from_product=tracking_item_from_product,
    )


def _render_cart_fragment(request, items, subtotal, discount_percent, discount_amount, total, status=200):
    """Render either cart page or cart panel fragment based on HTMX target."""
    target = (request.headers.get("HX-Target") or "").strip()
    template = "shopfront/partials/cart_content.html" if target == "cart-root" else "shopfront/partials/cart_panel.html"
    return render(
        request,
        template,
        {
            "items": items,
            "subtotal": subtotal,
            "discount_percent": discount_percent,
            "discount_amount": discount_amount,
            "total": total,
            "seller_groups": [],
            "seller_count": 0,
        },
        status=status,
    )


def _attach_cart_badge_oob(request, response):
    """Append out-of-band cart badge fragment to an HTMX response body."""
    return _shared_attach_cart_badge_oob(request, response)
