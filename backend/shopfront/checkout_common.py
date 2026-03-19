"""Shared checkout view helpers."""

from __future__ import annotations

import logging
from uuid import uuid4

from django.template.loader import render_to_string

from commerce.models import DeliveryAddress, LegalEntityMembership

from .cart_checkout_service import (
    cart_badge_context as _cart_badge_context,
    cart_summary as _cart_summary,
    checkout_addresses_queryset,
    checkout_cart_tracking_payload,
    checkout_company_snapshots,
    checkout_identity_defaults,
)
from .checkout_flow_service import build_checkout_context as _build_checkout_context, ensure_checkout_idempotency_key
from .checkout_support import (
    checkout_error_tracking_payload as _checkout_error_tracking_payload,
    checkout_step_tracking_payload as _checkout_step_tracking_payload,
    demo_payments_enabled as _demo_payments_enabled,
    tracking_item_from_product as _tracking_item_from_product,
)

log = logging.getLogger("shopfront")


def truncate_text(value: str, limit: int = 160) -> str:
    text = (value or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def default_og_image(request) -> str:
    return request.build_absolute_uri("/static/shopfront/big_logo.png")


def seo_context(
    request,
    *,
    title: str,
    description: str,
    canonical: str | None = None,
    robots: str = "index,follow",
    og_type: str = "website",
    og_image: str | None = None,
):
    canonical_url = canonical or request.build_absolute_uri(request.path)
    return {
        "seo_title": title,
        "seo_description": truncate_text(description, 170),
        "seo_canonical": canonical_url,
        "seo_robots": robots,
        "seo_og_type": og_type,
        "seo_og_image": og_image or default_og_image(request),
    }


def build_checkout_context(req, form_data=None, checkout_error=None):
    cart_ctx = _cart_summary(req)
    memberships = LegalEntityMembership.objects.none()
    addresses = DeliveryAddress.objects.none()
    individual_default_name = ""
    individual_default_email = ""
    if req.user.is_authenticated:
        memberships = LegalEntityMembership.objects.select_related("legal_entity").filter(user=req.user)
        addresses = checkout_addresses_queryset(req)
        individual_default_name, individual_default_email = checkout_identity_defaults(req)
    company_snapshots = checkout_company_snapshots(req, memberships)
    checkout_idem_key = ensure_checkout_idempotency_key(req, lambda: uuid4().hex)
    return _build_checkout_context(
        request=req,
        cart_ctx=cart_ctx,
        memberships=memberships,
        addresses=addresses,
        form_data=form_data,
        checkout_error=checkout_error or "",
        checkout_idem_key=checkout_idem_key,
        individual_default_name=individual_default_name,
        individual_default_email=individual_default_email,
        company_snapshots=company_snapshots,
        checkout_step_tracking_payload=_checkout_step_tracking_payload(
            "details",
            items=cart_ctx["items"],
            total=cart_ctx["total"],
            seller_count=cart_ctx["seller_count"],
        ),
        checkout_error_tracking_payload=_checkout_error_tracking_payload(
            checkout_error or "",
            customer_type=str((form_data or {}).get("customer_type") or ""),
            payment_method=str((form_data or {}).get("payment_method") or ""),
            items=cart_ctx["items"],
            total=cart_ctx["total"],
            seller_count=cart_ctx["seller_count"],
        ),
        checkout_cart_tracking_payload=checkout_cart_tracking_payload(cart_ctx, _tracking_item_from_product),
        demo_payments_enabled=_demo_payments_enabled(),
    )


def attach_cart_badge_oob(request, response):
    badge_html = render_to_string("shopfront/partials/cart_badge_oob.html", _cart_badge_context(request), request=request)
    content = response.content.decode(response.charset or "utf-8")
    response.content = (content + badge_html).encode(response.charset or "utf-8")
    return response
