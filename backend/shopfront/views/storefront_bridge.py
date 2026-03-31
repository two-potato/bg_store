"""Additive JSON bridge for Next.js storefront migration."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Mapping
from decimal import Decimal
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie

from catalog.models import Product
from commerce.models import DeliveryAddress, LegalEntityCreationRequest, LegalEntityMembership
from core.logging_utils import log_calls
from orders.models import Order
from shopfront.models import FavoriteProduct, SavedList, SavedListItem, SavedSearch
from shopfront.saved_list_service import FavoriteOperationService, SavedListOperationService, SavedSearchService
from users.forms import AddressForm, NotificationPreferencesForm, ProfileForm
from users.models import UserProfile
from users.views.helpers import (
    _approval_approved_count,
    _approval_required_count,
    _company_workspace_rows,
    _notification_feed,
    _visible_orders_queryset,
    approver_memberships_for_company,
    ensure_approval_policy,
    ensure_company_workspace,
)

from ..cart_checkout_service import cart_badge_context, cart_summary
from ..cart_mutation_service import add_to_cart_session, clear_cart_session, remove_from_cart_session, update_cart_session
from ..cart_store import merge_session_cart_with_persistent
from ..catalog_selectors import ordered_products_with_related
from .constants import log as analytics_log

log = logging.getLogger("shopfront")


def _json_error(*, error: str, status: int, login_url: str | None = None):
    payload: dict[str, object] = {"ok": False, "error": error}
    if login_url:
        payload["login_url"] = login_url
    return JsonResponse(payload, status=status)


def _validation_error_payload(form) -> dict[str, object]:
    fields: dict[str, list[str]] = {}
    for field, errors in form.errors.items():
        if field == "__all__":
            continue
        fields[field] = [str(error) for error in errors]
    non_field_errors = [str(error) for error in form.non_field_errors()]
    return {
        "ok": False,
        "error": "validation_error",
        "fields": fields,
        "non_field_errors": non_field_errors,
    }


def _money(value: Decimal | int | float | str) -> str:
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return str(value)


def _request_payload(request) -> tuple[dict[str, object], str | None]:
    content_type = (request.content_type or "").lower()
    if "application/json" not in content_type:
        return request.POST.dict(), None
    if not request.body:
        return {}, None
    try:
        parsed = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}, "invalid_json"
    if not isinstance(parsed, dict):
        return {}, "invalid_json"
    return parsed, None


def _read_int(payload: Mapping[str, object], field: str, *, default: int | None = None) -> int | None:
    raw = payload.get(field)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _login_url(request) -> str:
    next_target = _resolve_login_next_target(request)
    return f"/account/login/?{urlencode({'next': next_target})}"


def _resolve_login_next_target(request) -> str:
    referer = (request.headers.get("Referer") or "").strip()
    if referer:
        referer_url = urlsplit(referer)
        referer_target = f"{referer_url.path}{f'?{referer_url.query}' if referer_url.query else ''}"
        if referer_target.startswith("/") and not referer_target.startswith("/api/storefront/"):
            if url_has_allowed_host_and_scheme(
                referer,
                allowed_hosts={request.get_host(), request.get_host().split(":")[0], *getattr(settings, "ALLOWED_HOSTS", [])},
                require_https=False,
            ):
                return referer_target

    path = request.path or "/"
    api_path_matchers: list[tuple[re.Pattern[str], str | Callable[[re.Match[str]], str]]] = [
        (re.compile(r"^/api/storefront/orders/(?P<order_id>\d+)/(?:reorder/)?$"), lambda m: f"/account/orders/{m.group('order_id')}/"),
        (re.compile(r"^/api/storefront/account(?:/.*)?$"), "/account/"),
        (re.compile(r"^/api/storefront/cart(?:/.*)?$"), "/cart/"),
        (re.compile(r"^/api/storefront/tools/favorites(?:/.*)?$"), "/account/favorites/"),
        (
            re.compile(r"^/api/storefront/tools/lists/(?P<list_id>\d+)/(?:add/|remove-item/|move-to-cart/|toggle-public/|delete/)?$"),
            lambda m: f"/account/lists/{m.group('list_id')}/",
        ),
        (re.compile(r"^/api/storefront/tools/lists/$"), "/account/lists/"),
        (re.compile(r"^/api/storefront/tools/saved-searches(?:/\d+/delete/)?/$"), "/account/saved-searches/"),
    ]
    for pattern, replacement in api_path_matchers:
        matched = pattern.match(path)
        if not matched:
            continue
        if callable(replacement):
            return replacement(matched)
        return replacement
    return "/"


def _coerce_bool(raw, *, default: bool = False) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _string(raw, *, default: str = "") -> str:
    if raw is None:
        return default
    return str(raw).strip()


def _auth_user_payload(user) -> dict[str, object]:
    profile = getattr(user, "profile", None)
    store = getattr(user, "seller_store", None)
    full_name = ""
    phone = ""
    contact_email = ""
    role = None
    telegram_id = None
    telegram_username = None
    discount = "0.00"
    if profile is not None:
        full_name = profile.full_name or user.get_full_name() or ""
        phone = profile.phone or ""
        contact_email = profile.contact_email or ""
        role = profile.role
        telegram_id = profile.telegram_id
        telegram_username = profile.telegram_username
        discount = _money(profile.discount or Decimal("0.00"))
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email or "",
        "full_name": full_name,
        "phone": phone,
        "contact_email": contact_email,
        "role": role,
        "discount": discount,
        "seller_store": {
            "id": getattr(store, "id", None),
            "name": getattr(store, "name", "") if store else "",
            "slug": getattr(store, "slug", "") if store else "",
        },
        "telegram": {
            "id": telegram_id,
            "username": telegram_username or "",
            "linked": bool(telegram_id),
        },
    }


def _settings_payload(profile: UserProfile) -> dict[str, object]:
    user = profile.user
    return {
        "full_name": profile.full_name or "",
        "contact_email": profile.contact_email or "",
        "phone": profile.phone or "",
        "photo_url": profile.photo.url if profile.photo else "",
        "username": user.username,
        "email": user.email or "",
        "role": profile.role,
        "discount": _money(profile.discount or Decimal("0.00")),
        "telegram": {
            "id": profile.telegram_id,
            "username": profile.telegram_username or "",
            "linked": bool(profile.telegram_id),
        },
    }


def _preferences_payload(profile: UserProfile) -> dict[str, object]:
    return {
        "notify_email_orders": bool(profile.notify_email_orders),
        "notify_email_marketing": bool(profile.notify_email_marketing),
        "notify_telegram_orders": bool(profile.notify_telegram_orders),
        "notify_telegram_marketing": bool(profile.notify_telegram_marketing),
        "telegram_linked": bool(profile.telegram_id),
    }


def _address_payload(address: DeliveryAddress) -> dict[str, object]:
    return {
        "id": address.id,
        "legal_entity": {
            "id": address.legal_entity_id,
            "name": address.legal_entity.name,
        },
        "label": address.label,
        "country": address.country,
        "city": address.city,
        "street": address.street,
        "postcode": address.postcode,
        "details": address.details or "",
        "latitude": float(address.latitude) if address.latitude is not None else None,
        "longitude": float(address.longitude) if address.longitude is not None else None,
        "is_default": bool(address.is_default),
        "updated_at": address.updated_at.isoformat(),
    }


def _product_card_payload(product: Product, *, qty: int | None = None, item_id: int | None = None) -> dict[str, object]:
    payload = {
        "id": product.id,
        "slug": product.slug,
        "sku": product.sku,
        "name": product.name,
        "image_url": _product_image_url(product),
        "price": _money(Decimal(str(product.display_price))),
        "stock_qty": int(product.display_stock_qty or 0),
        "min_order_qty": int(product.display_min_order_qty or 1),
        "brand_name": getattr(getattr(product, "brand", None), "name", "") or "",
    }
    if qty is not None:
        payload["qty"] = int(qty)
    if item_id is not None:
        payload["item_id"] = int(item_id)
    return payload


def _analytics_client_ip(request) -> str:
    forwarded_for = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    if forwarded_for and getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        return forwarded_for
    return request.META.get("REMOTE_ADDR", "unknown")


def _analytics_same_origin_or_allowed_host(request) -> bool:
    origin = (request.headers.get("Origin") or "").strip()
    if not origin:
        return True
    allowed_hosts = {
        request.get_host(),
        request.get_host().split(":")[0],
        *getattr(settings, "ALLOWED_HOSTS", []),
    }
    return url_has_allowed_host_and_scheme(origin, allowed_hosts=allowed_hosts, require_https=False)


def _analytics_throttled(request, *, scope: str) -> bool:
    limit = max(1, int(getattr(settings, "ANALYTICS_INGEST_RATE_LIMIT", 180)))
    window_seconds = max(1, int(getattr(settings, "ANALYTICS_INGEST_WINDOW_SECONDS", 60)))
    session_key = request.session.session_key or "anon"
    cache_key = f"shopfront:analytics:{scope}:{_analytics_client_ip(request)}:{session_key}"
    if cache.add(cache_key, 1, timeout=window_seconds):
        return False
    try:
        current = cache.incr(cache_key)
    except ValueError:
        current = int(cache.get(cache_key, 0) or 0) + 1
        cache.set(cache_key, current, timeout=window_seconds)
    return int(current) > limit


def _product_image_url(product: Product) -> str:
    prefetched_images = getattr(product, "prefetched_images", None) or []
    if prefetched_images:
        return prefetched_images[0].public_url
    first = product.images.order_by("ordering", "id").only("url").first()
    return first.public_url if first else ""


def _cart_item_payload(item: dict[str, object]) -> dict[str, object]:
    product: Product = item["p"]  # type: ignore[assignment]
    qty = int(item["qty"])  # type: ignore[arg-type]
    row_total = item["row"]  # type: ignore[assignment]
    seller_store = item.get("seller_store")
    seller_user = getattr(product, "seller", None)
    return {
        "product": {
            "id": product.id,
            "slug": product.slug,
            "name": product.name,
            "sku": product.sku,
            "brand": getattr(getattr(product, "brand", None), "name", "") or "",
            "category": getattr(getattr(product, "category", None), "name", "") or "",
            "image_url": _product_image_url(product),
            "price": _money(Decimal(str(product.display_price))),
            "stock_qty": int(product.display_stock_qty or 0),
            "min_order_qty": int(product.display_min_order_qty or 1),
        },
        "qty": qty,
        "row_total": _money(row_total),  # type: ignore[arg-type]
        "seller": {
            "id": getattr(seller_store, "id", None) or getattr(seller_user, "id", None),
            "name": (
                getattr(seller_store, "name", "")
                or getattr(seller_user, "username", "")
                or "Servio"
            ),
            "slug": getattr(seller_store, "slug", "") or "",
        },
    }


def _cart_payload(request) -> dict[str, object]:
    cart_ctx = cart_summary(request)
    items = [_cart_item_payload(item) for item in cart_ctx["items"]]
    seller_groups: list[dict[str, object]] = []
    for group in cart_ctx["seller_groups"]:
        seller_groups.append(
            {
                "title": group["title"],
                "slug": group["slug"],
                "subtotal": _money(group["subtotal"]),
                "items": [_cart_item_payload(item) for item in group["items"]],
            }
        )
    return {
        "items": items,
        "seller_groups": seller_groups,
        "seller_count": int(cart_ctx["seller_count"]),
        "cart_count": int(cart_ctx["cart_count"]),
        "is_empty": not bool(items),
        "subtotal": _money(cart_ctx["subtotal"]),
        "discount_percent": _money(cart_ctx["discount_percent"]),
        "discount_amount": _money(cart_ctx["discount_amount"]),
        "coupon_discount_amount": _money(cart_ctx["coupon_discount_amount"]),
        "profile_discount_amount": _money(cart_ctx["profile_discount_amount"]),
        "total": _money(cart_ctx["total"]),
        "coupon": {
            "code": cart_ctx["resolved_coupon_code"] or "",
            "validation_error": cart_ctx["coupon_validation_error"] or "",
        },
    }


def _order_short_payload(order: Order) -> dict[str, object]:
    return {
        "id": order.id,
        "status": order.status,
        "status_display": order.get_status_display(),
        "approval_status": order.approval_status,
        "approval_status_display": order.get_approval_status_display(),
        "payment_method": order.payment_method,
        "delivery_method": order.delivery_method,
        "subtotal": _money(order.subtotal),
        "discount_amount": _money(order.discount_amount),
        "total": _money(order.total),
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
        "legal_entity": {
            "id": order.legal_entity_id,
            "name": getattr(order.legal_entity, "name", "") if order.legal_entity_id else "",
        },
        "detail_url": f"/account/orders/{order.id}/",
    }


def _session_cart_qty(request, product_id: int) -> int:
    session_cart = request.session.get("cart", {})
    try:
        return max(0, int((session_cart.get(str(product_id), {}) or {}).get("qty", 0)))
    except (TypeError, ValueError, AttributeError):
        return 0


def _order_item_payload(item) -> dict[str, object]:
    product = item.product
    active_qty = int(getattr(item, "active_qty", item.qty or 0) or 0)
    row_total = (Decimal(str(item.price)) * Decimal(max(0, active_qty))).quantize(Decimal("0.01"))
    return {
        "id": item.id,
        "product_id": item.product_id,
        "name": item.name,
        "qty": int(item.qty or 0),
        "canceled_qty": int(item.canceled_qty or 0),
        "active_qty": active_qty,
        "price": _money(item.price),
        "row_total": _money(row_total),
        "seller_offer_id": item.seller_offer_id,
        "product": {
            "id": product.id,
            "slug": product.slug,
            "name": product.name,
            "sku": product.sku,
            "image_url": _product_image_url(product),
        },
    }


def _order_detail_payload(request, order: Order) -> dict[str, object]:
    company = ensure_company_workspace(order.legal_entity) if order.legal_entity_id else None
    approval_policy = ensure_approval_policy(company) if company else None
    can_approve = bool(
        company
        and request.user.is_authenticated
        and approver_memberships_for_company(company).filter(user=request.user).exists()
    )

    items = [_order_item_payload(item) for item in order.items.all()]
    seller_splits = [
        {
            "id": split.id,
            "seller_id": split.seller_id,
            "seller_name": split.seller.username,
            "seller_store_name": split.seller_store_name,
            "items_count": int(split.items_count or 0),
            "subtotal": _money(split.subtotal),
            "status": split.status,
            "status_display": split.get_status_display(),
        }
        for split in order.seller_splits.all()
    ]

    shipments: list[dict[str, object]] = []
    for seller_order in order.seller_orders.all():
        for shipment in seller_order.shipments.all():
            shipments.append(
                {
                    "id": shipment.id,
                    "seller_order_id": seller_order.id,
                    "seller_id": seller_order.seller_id,
                    "seller_name": seller_order.seller.username,
                    "seller_store_name": seller_order.seller_store_name,
                    "tracking_number": shipment.tracking_number,
                    "delivery_method": shipment.delivery_method,
                    "warehouse_name": shipment.warehouse_name,
                    "status": shipment.status,
                    "status_display": shipment.get_status_display(),
                    "packed_at": shipment.packed_at.isoformat() if shipment.packed_at else None,
                    "shipped_at": shipment.shipped_at.isoformat() if shipment.shipped_at else None,
                    "delivered_at": shipment.delivered_at.isoformat() if shipment.delivered_at else None,
                }
            )

    approval_logs = [
        {
            "id": log_row.id,
            "actor_id": log_row.actor_id,
            "actor_username": log_row.actor.username,
            "decision": log_row.decision,
            "decision_display": log_row.get_decision_display(),
            "comment": log_row.comment,
            "created_at": log_row.created_at.isoformat(),
        }
        for log_row in order.approval_logs.all()
    ]

    claims = list(order.claims.all())
    support_tickets = list(order.support_tickets.all())
    has_seller_orders = bool(order.seller_orders.all())
    has_claims = bool(claims)
    paid_or_later = order.status in {Order.Status.PAID, Order.Status.DELIVERING, Order.Status.DELIVERED}
    delivering_or_delivered = order.status in {Order.Status.DELIVERING, Order.Status.DELIVERED}
    timeline = [
        {
            "key": "created",
            "title": "Created",
            "state": "done",
            "label": order.created_at.isoformat(),
            "timestamp": order.created_at.isoformat(),
        },
        {
            "key": "sent_for_approval",
            "title": "Sent for approval",
            "state": "done"
            if order.approval_status
            in {Order.ApprovalStatus.PENDING, Order.ApprovalStatus.APPROVED, Order.ApprovalStatus.REJECTED}
            else "pending",
            "label": order.get_approval_status_display(),
            "timestamp": None,
        },
        {
            "key": "approved_or_rejected",
            "title": "Approved / rejected",
            "state": "done"
            if order.approval_status == Order.ApprovalStatus.APPROVED
            else "issue"
            if order.approval_status == Order.ApprovalStatus.REJECTED
            else "pending",
            "label": order.approved_at.isoformat() if order.approved_at else "Ожидает решения",
            "timestamp": order.approved_at.isoformat() if order.approved_at else None,
        },
        {
            "key": "invoiced",
            "title": "Invoiced",
            "state": "done" if order.payment_method == Order.PaymentMethod.INVOICE else "pending",
            "label": "По счёту" if order.payment_method == Order.PaymentMethod.INVOICE else "Без invoice flow",
            "timestamp": None,
        },
        {
            "key": "paid",
            "title": "Paid",
            "state": "done" if paid_or_later else "pending",
            "label": order.get_status_display(),
            "timestamp": None,
        },
        {
            "key": "packed",
            "title": "Packed",
            "state": "done" if has_seller_orders else "pending",
            "label": "Поставщики приняли заказ" if has_seller_orders else "Ожидает распределения",
            "timestamp": None,
        },
        {
            "key": "shipped",
            "title": "Shipped",
            "state": "done" if delivering_or_delivered else "pending",
            "label": "Выполняется" if delivering_or_delivered else "Ещё не отгружен",
            "timestamp": None,
        },
        {
            "key": "delivered",
            "title": "Delivered",
            "state": "done" if order.status == Order.Status.DELIVERED else "pending",
            "label": "Заказ завершён" if order.status == Order.Status.DELIVERED else "В пути",
            "timestamp": None,
        },
        {
            "key": "claim_opened_or_resolved",
            "title": "Claim opened / resolved",
            "state": "issue" if has_claims else "pending",
            "label": f"{len(claims)} обращений" if has_claims else "Без претензий",
            "timestamp": None,
        },
    ]
    open_claim_statuses = {order.claims.model.Status.OPEN, order.claims.model.Status.IN_REVIEW}
    open_support_statuses = {
        order.support_tickets.model.Status.OPEN,
        order.support_tickets.model.Status.IN_PROGRESS,
    }
    claims_payload = [
        {
            "id": claim.id,
            "claim_type": claim.claim_type,
            "claim_type_display": claim.get_claim_type_display(),
            "status": claim.status,
            "status_display": claim.get_status_display(),
            "message": claim.message,
            "seller_response": claim.seller_response,
            "resolution_comment": claim.resolution_comment,
            "created_by_username": claim.created_by.username,
            "responded_by_username": claim.responded_by.username if claim.responded_by_id else "",
            "created_at": claim.created_at.isoformat(),
            "updated_at": claim.updated_at.isoformat(),
        }
        for claim in claims[:5]
    ]
    support_payload = [
        {
            "id": ticket.id,
            "topic": ticket.topic,
            "topic_display": ticket.get_topic_display(),
            "status": ticket.status,
            "status_display": ticket.get_status_display(),
            "subject": ticket.subject,
            "message": ticket.message,
            "resolution_comment": ticket.resolution_comment,
            "created_by_username": ticket.created_by.username,
            "created_at": ticket.created_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat(),
        }
        for ticket in support_tickets[:5]
    ]

    demo_enabled = bool(getattr(settings, "ENABLE_DEMO_PAYMENTS", settings.DEBUG))
    fake_payment = getattr(order, "fake_payment", None)
    retry_url = ""
    if (
        demo_enabled
        and order.placed_by_id == request.user.id
        and order.payment_method in {Order.PaymentMethod.MIR_CARD, Order.PaymentMethod.ONLINE_CARD}
        and fake_payment is not None
    ):
        if order.payment_method == Order.PaymentMethod.ONLINE_CARD:
            retry_url = f"/payments/online/{order.id}/"
        else:
            retry_url = f"/payments/fake/{order.id}/"

    return {
        "id": order.id,
        "status": order.status,
        "status_display": order.get_status_display(),
        "split_status": order.split_status,
        "split_status_display": order.get_split_status_display(),
        "approval_status": order.approval_status,
        "approval_status_display": order.get_approval_status_display(),
        "customer_type": order.customer_type,
        "customer_type_display": order.get_customer_type_display(),
        "payment_method": order.payment_method,
        "payment_method_display": order.get_payment_method_display(),
        "delivery_method": order.delivery_method,
        "delivery_method_display": order.get_delivery_method_display(),
        "subtotal": _money(order.subtotal),
        "discount_amount": _money(order.discount_amount),
        "total": _money(order.total),
        "customer_comment": order.customer_comment,
        "coupon_code": order.coupon_code,
        "source_channel": order.source_channel,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
        "approved_at": order.approved_at.isoformat() if order.approved_at else None,
        "approved_by": {
            "id": order.approved_by_id,
            "username": order.approved_by.username if order.approved_by_id else "",
        },
        "placed_by": {
            "id": order.placed_by_id,
            "username": order.placed_by.username if order.placed_by_id else "",
        },
        "legal_entity": {
            "id": order.legal_entity_id,
            "name": getattr(order.legal_entity, "name", "") if order.legal_entity_id else "",
        },
        "delivery_address": {
            "id": order.delivery_address_id,
            "label": getattr(order.delivery_address, "label", "") if order.delivery_address_id else "",
            "city": getattr(order.delivery_address, "city", "") if order.delivery_address_id else "",
            "street": getattr(order.delivery_address, "street", "") if order.delivery_address_id else "",
            "postcode": getattr(order.delivery_address, "postcode", "") if order.delivery_address_id else "",
        },
        "items": items,
        "seller_splits": seller_splits,
        "approval": {
            "required_count": _approval_required_count(order),
            "approved_count": _approval_approved_count(order),
            "can_approve": can_approve,
            "policy": {
                "enabled": bool(approval_policy and approval_policy.is_enabled),
                "require_comment": bool(approval_policy and approval_policy.require_comment),
                "required_approvals_count": int(approval_policy.required_approvals_count) if approval_policy else 1,
                "max_pending_hours": int(approval_policy.max_pending_hours) if approval_policy else 24,
            },
            "logs": approval_logs,
        },
        "tracking": {
            "available": bool(shipments),
            "shipments": shipments,
            "tracking_url": f"/account/orders/{order.id}/tracking/",
        },
        "payment": {
            "demo_enabled": demo_enabled,
            "can_retry": bool(retry_url),
            "retry_url": retry_url,
            "invoice_url": f"/account/orders/{order.id}/invoice/",
            "fake_payment": {
                "provider_payment_id": fake_payment.provider_payment_id if fake_payment else "",
                "status": fake_payment.status if fake_payment else "",
                "status_display": fake_payment.get_status_display() if fake_payment else "",
                "last_event": fake_payment.last_event if fake_payment else "",
                "amount": _money(fake_payment.amount) if fake_payment else "0.00",
            },
        },
        "support": {
            "claims_count": len(claims),
            "open_claims_count": sum(1 for claim in claims if claim.status in open_claim_statuses),
            "support_tickets_count": len(support_tickets),
            "open_support_tickets_count": sum(
                1 for ticket in support_tickets if ticket.status in open_support_statuses
            ),
            "claims": claims_payload,
            "support_tickets": support_payload,
        },
        "timeline": timeline,
        "actions": {
            "can_reorder": bool(order.placed_by_id == request.user.id),
            "can_cancel": bool(
                order.placed_by_id == request.user.id
                and order.status not in {Order.Status.CANCELED, Order.Status.DELIVERED}
            ),
            "reorder_url": f"/api/storefront/orders/{order.id}/reorder/",
            "legacy_detail_url": f"/account/orders/{order.id}/",
        },
    }


@method_decorator(ensure_csrf_cookie, name="dispatch")
class StorefrontSessionBootstrapView(View):
    """Session/bootstrap endpoint for browser-based Next storefront."""

    @log_calls(log)
    def get(self, request):
        csrf_token = get_token(request)
        user_payload: dict[str, object] | None = None
        if request.user.is_authenticated:
            merged_cart = merge_session_cart_with_persistent(request.user, request.session.get("cart", {}))
            request.session["cart"] = merged_cart
            request.session.modified = True
            user_payload = _auth_user_payload(request.user)
        badge_ctx = cart_badge_context(request)
        response = JsonResponse(
            {
                "ok": True,
                "session": {
                    "authenticated": bool(request.user.is_authenticated),
                    "session_key": request.session.session_key or "",
                    "csrf_token": csrf_token,
                },
                "user": user_payload,
                "cart_badge": {
                    "count": int(badge_ctx["count"]),
                    "subtotal": _money(badge_ctx["subtotal"]),
                },
                "urls": {
                    "login": _login_url(request),
                    "logout": "/account/logout/",
                    "account": "/account/",
                    "cart": "/cart/",
                },
            }
        )
        response["Cache-Control"] = "no-store"
        response["Vary"] = "Cookie"
        return response


class StorefrontCartView(View):
    """Read cart JSON for Next storefront cart page."""

    @log_calls(log)
    def get(self, request):
        return JsonResponse({"ok": True, "cart": _cart_payload(request)})


class StorefrontCartAddView(View):
    """Add an item to session cart and return fresh cart snapshot."""

    @log_calls(log)
    def post(self, request):
        payload, error = _request_payload(request)
        if error:
            return _json_error(error=error, status=400)
        product_id = _read_int(payload, "product_id")
        qty = _read_int(payload, "qty", default=1)
        if not product_id or product_id <= 0 or qty is None:
            return _json_error(error="invalid_payload", status=400)
        try:
            mutation = add_to_cart_session(request=request, product_id=product_id, qty=max(1, qty), logger=log)
        except Product.DoesNotExist:
            return _json_error(error="product_not_found", status=404)
        return JsonResponse(
            {
                "ok": True,
                "item": {
                    "product_id": product_id,
                    "qty": int(mutation["current_qty"]),
                    "line_value": _money(mutation["line_value"]),
                },
                "cart": _cart_payload(request),
            }
        )


class StorefrontCartUpdateView(View):
    """Update line item quantity (set/inc/dec) and return fresh cart snapshot."""

    @log_calls(log)
    def post(self, request):
        payload, error = _request_payload(request)
        if error:
            return _json_error(error=error, status=400)
        product_id = _read_int(payload, "product_id")
        op = str(payload.get("op") or "set").strip().lower()
        if op not in {"set", "inc", "dec"}:
            op = "set"
        if not product_id or product_id <= 0:
            return _json_error(error="invalid_product", status=400)
        mutation = update_cart_session(
            request=request,
            product_id=product_id,
            op=op,
            requested_qty=payload.get("qty"),
            logger=log,
        )
        if mutation["missing"]:
            return _json_error(error="item_not_in_cart", status=404)
        return JsonResponse(
            {
                "ok": True,
                "item": {
                    "product_id": product_id,
                    "qty": int(mutation["qty"]),
                },
                "cart": _cart_payload(request),
            }
        )


class StorefrontCartRemoveView(View):
    """Remove a line item from cart and return fresh cart snapshot."""

    @log_calls(log)
    def post(self, request):
        payload, error = _request_payload(request)
        if error:
            return _json_error(error=error, status=400)
        product_id = _read_int(payload, "product_id")
        if not product_id or product_id <= 0:
            return _json_error(error="invalid_product", status=400)
        remove_from_cart_session(request=request, product_id=product_id)
        return JsonResponse({"ok": True, "cart": _cart_payload(request)})


class StorefrontCartClearView(View):
    """Clear session cart and return empty cart snapshot."""

    @log_calls(log)
    def post(self, request):
        clear_cart_session(request=request)
        return JsonResponse({"ok": True, "cart": _cart_payload(request)})


class StorefrontOrderDetailView(View):
    """Order detail JSON contract for Next storefront buyer shell."""

    @log_calls(log)
    def get(self, request, order_id: int):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))

        order = (
            _visible_orders_queryset(request.user)
            .select_related("legal_entity", "delivery_address", "placed_by", "approved_by", "fake_payment")
            .prefetch_related(
                "items__seller_offer",
                "seller_splits__seller",
                "seller_orders__seller",
                "seller_orders__items",
                "seller_orders__shipments",
                "approval_logs__actor",
                "claims__created_by",
                "claims__responded_by",
                "support_tickets__created_by",
            )
            .filter(id=order_id)
            .first()
        )
        if not order:
            return _json_error(error="order_not_found", status=404)
        return JsonResponse({"ok": True, "order": _order_detail_payload(request, order)})


class StorefrontOrderReorderView(View):
    """Reorder bridge endpoint for order-detail-driven cart refill."""

    @log_calls(log)
    def post(self, request, order_id: int):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))

        order = (
            _visible_orders_queryset(request.user)
            .prefetch_related("items")
            .filter(id=order_id, placed_by=request.user)
            .first()
        )
        if not order:
            return _json_error(error="order_not_found", status=404)

        requested_by_product: dict[int, int] = {}
        product_name_by_id: dict[int, str] = {}
        for item in order.items.all():
            requested_qty = max(0, int(getattr(item, "active_qty", item.qty or 0) or 0))
            if requested_qty <= 0:
                continue
            requested_by_product[item.product_id] = requested_by_product.get(item.product_id, 0) + requested_qty
            product_name_by_id[item.product_id] = item.name

        added: list[dict[str, object]] = []
        adjusted: list[dict[str, object]] = []
        unavailable: list[dict[str, object]] = []
        total_requested_qty = 0
        total_added_qty = 0

        for product_id, requested_qty in requested_by_product.items():
            total_requested_qty += requested_qty
            before_qty = _session_cart_qty(request, product_id)
            try:
                mutation = add_to_cart_session(
                    request=request,
                    product_id=product_id,
                    qty=requested_qty,
                    logger=log,
                )
            except Product.DoesNotExist:
                unavailable.append(
                    {
                        "product_id": product_id,
                        "product_name": product_name_by_id.get(product_id, ""),
                        "requested_qty": requested_qty,
                        "reason": "product_not_found",
                    }
                )
                continue

            after_qty = int(mutation["current_qty"])
            added_qty = max(0, after_qty - before_qty)
            total_added_qty += added_qty
            row = {
                "product_id": product_id,
                "product_name": mutation["product"].name,
                "requested_qty": requested_qty,
                "added_qty": added_qty,
                "cart_qty": after_qty,
            }
            if added_qty <= 0:
                unavailable.append({**row, "reason": "out_of_stock_or_limit_reached"})
            elif added_qty < requested_qty:
                adjusted.append({**row, "reason": "stock_capped"})
            else:
                added.append(row)

        if total_requested_qty <= 0:
            result_type = "none"
        elif total_added_qty >= total_requested_qty:
            result_type = "full"
        elif total_added_qty > 0:
            result_type = "partial"
        else:
            result_type = "none"

        return JsonResponse(
            {
                "ok": True,
                "reorder": {
                    "order_id": order.id,
                    "result_type": result_type,
                    "summary": {
                        "requested_lines": len(requested_by_product),
                        "added_lines": len(added),
                        "adjusted_lines": len(adjusted),
                        "unavailable_lines": len(unavailable),
                        "total_requested_qty": total_requested_qty,
                        "total_added_qty": total_added_qty,
                    },
                    "added": added,
                    "adjusted": adjusted,
                    "unavailable": unavailable,
                    "cart_url": "/cart/",
                },
                "cart": _cart_payload(request),
            }
        )


class StorefrontFavoritesView(View):
    """Favorites page-level read/toggle contract for Next buyer tools."""

    @log_calls(log)
    def get(self, request):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        favorite_service = FavoriteOperationService(request.user)
        products = favorite_service.get_favorite_products(limit=300)
        return JsonResponse(
            {
                "ok": True,
                "favorites": [_product_card_payload(product) for product in products],
                "counts": {
                    "favorites": len(products),
                    "saved_lists": int(SavedList.objects.filter(user=request.user).count()),
                },
            }
        )


class StorefrontFavoriteToggleView(View):
    """Toggle favorite for one product."""

    @log_calls(log)
    def post(self, request):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        payload, error = _request_payload(request)
        if error:
            return _json_error(error=error, status=400)
        product_id = _read_int(payload, "product_id")
        if not product_id or product_id <= 0:
            return _json_error(error="invalid_product", status=400)
        product = Product.objects.filter(pk=product_id).first()
        if product is None:
            return _json_error(error="product_not_found", status=404)
        _, created = FavoriteOperationService(request.user).toggle_favorite(product=product, request=request)
        return JsonResponse(
            {
                "ok": True,
                "favorited": bool(created),
                "product_id": product_id,
            }
        )


class StorefrontSavedListsView(View):
    """Read/create saved lists for buyer tools."""

    @log_calls(log)
    def get(self, request):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        saved_lists = (
            SavedList.objects.filter(user=request.user)
            .prefetch_related("items")
            .order_by("-updated_at", "-id")[:100]
        )
        return JsonResponse(
            {
                "ok": True,
                "saved_lists": [
                    {
                        "id": saved_list.id,
                        "name": saved_list.name,
                        "description": saved_list.description or "",
                        "source": saved_list.source,
                        "is_public": bool(saved_list.is_public),
                        "share_token": saved_list.share_token,
                        "items_count": int(saved_list.items.count()),
                        "updated_at": saved_list.updated_at.isoformat(),
                    }
                    for saved_list in saved_lists
                ],
            }
        )

    @log_calls(log)
    def post(self, request):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        payload, error = _request_payload(request)
        if error:
            return _json_error(error=error, status=400)
        service = SavedListOperationService(request.user)
        result = service.create_list(
            name=_string(payload.get("name")),
            description=_string(payload.get("description")),
            source=SavedList.Source.MANUAL,
        )
        if not result.success or not result.list_id:
            return _json_error(error="list_create_failed", status=400)
        saved_list = SavedList.objects.get(id=result.list_id, user=request.user)
        return JsonResponse(
            {
                "ok": True,
                "saved_list": {
                    "id": saved_list.id,
                    "name": saved_list.name,
                    "description": saved_list.description or "",
                    "source": saved_list.source,
                    "is_public": bool(saved_list.is_public),
                    "share_token": saved_list.share_token,
                },
            }
        )


class StorefrontSavedListDetailView(View):
    """Read/toggle/delete one saved list."""

    @log_calls(log)
    def get(self, request, list_id: int):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        saved_list = (
            SavedList.objects.filter(user=request.user, id=list_id)
            .prefetch_related("items__product__images", "items__product__brand")
            .first()
        )
        if saved_list is None:
            return _json_error(error="list_not_found", status=404)
        items = list(saved_list.items.all())
        products_by_id = {product.id: product for product in ordered_products_with_related([item.product_id for item in items], include_rating=True)}
        return JsonResponse(
            {
                "ok": True,
                "saved_list": {
                    "id": saved_list.id,
                    "name": saved_list.name,
                    "description": saved_list.description or "",
                    "source": saved_list.source,
                    "is_public": bool(saved_list.is_public),
                    "share_token": saved_list.share_token,
                    "share_url": f"/lists/shared/{saved_list.share_token}/",
                    "items": [
                        {
                            "id": item.id,
                            "quantity": int(item.quantity or 1),
                            "note": item.note or "",
                            "ordering": int(item.ordering or 0),
                            "product": _product_card_payload(products_by_id[item.product_id]),
                        }
                        for item in items
                        if item.product_id in products_by_id
                    ],
                },
            }
        )


class StorefrontSavedListAddItemView(View):
    """Add product into saved list with quantity."""

    @log_calls(log)
    def post(self, request, list_id: int):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        payload, error = _request_payload(request)
        if error:
            return _json_error(error=error, status=400)
        product_id = _read_int(payload, "product_id")
        qty = _read_int(payload, "qty", default=1)
        if not product_id or product_id <= 0 or qty is None:
            return _json_error(error="invalid_payload", status=400)
        saved_list = SavedList.objects.filter(user=request.user, id=list_id).first()
        if saved_list is None:
            return _json_error(error="list_not_found", status=404)
        product = Product.objects.filter(pk=product_id).first()
        if product is None:
            return _json_error(error="product_not_found", status=404)
        qty_value = max(1, qty)
        service = SavedListOperationService(request.user)
        service_result = service.add_products_to_list(
            list_id=saved_list.id,
            product_ids=[product.id],
            quantities={product.id: qty_value},
        )
        if not service_result.success:
            return _json_error(error="list_not_found", status=404)
        item = SavedListItem.objects.get(saved_list=saved_list, product=product)
        if item.quantity != qty_value:
            item.quantity = qty_value
            item.save(update_fields=["quantity", "updated_at"])
        return JsonResponse(
            {
                "ok": True,
                "item": {
                    "id": item.id,
                    "quantity": int(item.quantity or 1),
                    "product": _product_card_payload(product),
                },
            }
        )


class StorefrontSavedListRemoveItemView(View):
    """Remove one item from saved list."""

    @log_calls(log)
    def post(self, request, list_id: int):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        payload, error = _request_payload(request)
        if error:
            return _json_error(error=error, status=400)
        item_id = _read_int(payload, "item_id")
        if not item_id or item_id <= 0:
            return _json_error(error="invalid_item_id", status=400)
        deleted, _ = SavedListItem.objects.filter(
            id=item_id,
            saved_list_id=list_id,
            saved_list__user=request.user,
        ).delete()
        if not deleted:
            return _json_error(error="item_not_found", status=404)
        return JsonResponse({"ok": True})


class StorefrontSavedListMoveToCartView(View):
    """Move saved list items into cart using existing cart domain behavior."""

    @log_calls(log)
    def post(self, request, list_id: int):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        saved_list = (
            SavedList.objects.filter(user=request.user, id=list_id)
            .prefetch_related("items")
            .first()
        )
        if saved_list is None:
            return _json_error(error="list_not_found", status=404)
        moved = 0
        for item in saved_list.items.all():
            try:
                add_to_cart_session(
                    request=request,
                    product_id=item.product_id,
                    qty=max(1, int(item.quantity or 1)),
                    logger=log,
                )
                moved += 1
            except Product.DoesNotExist:
                continue
        return JsonResponse(
            {
                "ok": True,
                "moved_items": moved,
                "cart": _cart_payload(request),
            }
        )


class StorefrontSavedListTogglePublicView(View):
    """Toggle public/private status for saved list."""

    @log_calls(log)
    def post(self, request, list_id: int):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        service = SavedListOperationService(request.user)
        result = service.toggle_list_public(list_id)
        if not result.success:
            return _json_error(error="list_not_found", status=404)
        saved_list = SavedList.objects.filter(user=request.user, id=list_id).first()
        return JsonResponse(
            {
                "ok": True,
                "is_public": bool(saved_list and saved_list.is_public),
                "share_token": saved_list.share_token if saved_list else "",
            }
        )


class StorefrontSavedListDeleteView(View):
    """Delete saved list."""

    @log_calls(log)
    def post(self, request, list_id: int):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        service = SavedListOperationService(request.user)
        result = service.delete_list(list_id)
        if not result.success:
            return _json_error(error="list_not_found", status=404)
        return JsonResponse({"ok": True})


class StorefrontSavedSearchesView(View):
    """Read/create saved searches for buyer tools."""

    @log_calls(log)
    def get(self, request):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        searches = (
            SavedSearch.objects.filter(user=request.user)
            .order_by("-created_at")[:200]
        )
        return JsonResponse(
            {
                "ok": True,
                "saved_searches": [
                    {
                        "id": search.id,
                        "name": search.name,
                        "querystring": search.querystring,
                        "created_at": search.created_at.isoformat(),
                    }
                    for search in searches
                ],
            }
        )

    @log_calls(log)
    def post(self, request):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        payload, error = _request_payload(request)
        if error:
            return _json_error(error=error, status=400)
        service = SavedSearchService(request.user)
        result = service.save_search(
            querystring=_string(payload.get("querystring")),
            name=_string(payload.get("name"), default="Мой фильтр"),
        )
        if not result.success or not result.list_id:
            return _json_error(error="invalid_querystring", status=400)
        saved_search = SavedSearch.objects.get(id=result.list_id, user=request.user)
        return JsonResponse(
            {
                "ok": True,
                "saved_search": {
                    "id": saved_search.id,
                    "name": saved_search.name,
                    "querystring": saved_search.querystring,
                    "created_at": saved_search.created_at.isoformat(),
                },
            }
        )


class StorefrontSavedSearchDeleteView(View):
    """Delete one saved search."""

    @log_calls(log)
    def post(self, request, search_id: int):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        service = SavedSearchService(request.user)
        result = service.delete_search(search_id)
        if not result.success:
            return _json_error(error="saved_search_not_found", status=404)
        return JsonResponse({"ok": True})


class StorefrontWaveAnalyticsIngestView(View):
    """Minimal analytics ingest for cart/account/orders Next wave."""

    allowed_events = {
        "cart_viewed",
        "cart_qty_incremented",
        "cart_qty_decremented",
        "cart_item_removed",
        "cart_cleared",
        "cart_checkout_clicked",
        "account_dashboard_viewed",
        "orders_list_viewed",
        "order_detail_viewed",
        "order_tracking_viewed",
        "order_reorder_clicked",
        "order_cancel_submitted",
        "invoice_download_clicked",
        "claim_created",
        "support_ticket_created",
        "address_created",
        "legal_request_created",
        "favorites_viewed",
        "favorite_toggled",
        "saved_list_created",
        "saved_list_deleted",
        "saved_list_item_added",
        "saved_list_item_removed",
        "saved_list_moved_to_cart",
        "saved_search_saved",
        "saved_search_deleted",
    }

    @log_calls(analytics_log)
    def post(self, request):
        if not _analytics_same_origin_or_allowed_host(request):
            return _json_error(error="invalid_origin", status=403)
        if _analytics_throttled(request, scope="next-wave"):
            return _json_error(error="rate_limited", status=429)
        payload, error = _request_payload(request)
        if error:
            return _json_error(error=error, status=400)
        event_name = _string(payload.get("event"))
        if event_name not in self.allowed_events:
            return _json_error(error="unsupported_event", status=400)
        analytics_log.info(
            "storefront_wave_analytics_event",
            extra={
                "event": event_name,
                "user_id": request.user.id if getattr(request.user, "is_authenticated", False) else None,
                "session_key": request.session.session_key or "",
                "surface": _string(payload.get("surface"), default="unknown"),
                "payload": payload,
            },
        )
        return HttpResponse(status=204)


class StorefrontAccountSettingsView(View):
    """Buyer settings contract for Next account shell."""

    @log_calls(log)
    def get(self, request):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return JsonResponse({"ok": True, "settings": _settings_payload(profile)})

    @log_calls(log)
    def post(self, request):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        payload, error = _request_payload(request)
        if error:
            return _json_error(error=error, status=400)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        form = ProfileForm(
            data={
                "full_name": _string(payload.get("full_name"), default=profile.full_name),
                "contact_email": _string(payload.get("contact_email"), default=profile.contact_email),
                "phone": _string(payload.get("phone"), default=profile.phone or ""),
            },
            instance=profile,
        )
        if not form.is_valid():
            return JsonResponse(_validation_error_payload(form), status=400)
        profile = form.save()
        return JsonResponse({"ok": True, "settings": _settings_payload(profile)})


class StorefrontAccountPreferencesView(View):
    """Buyer notification preferences contract."""

    @log_calls(log)
    def get(self, request):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return JsonResponse({"ok": True, "preferences": _preferences_payload(profile)})

    @log_calls(log)
    def post(self, request):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        payload, error = _request_payload(request)
        if error:
            return _json_error(error=error, status=400)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        form = NotificationPreferencesForm(
            data={
                "notify_email_orders": _coerce_bool(
                    payload.get("notify_email_orders"),
                    default=bool(profile.notify_email_orders),
                ),
                "notify_email_marketing": _coerce_bool(
                    payload.get("notify_email_marketing"),
                    default=bool(profile.notify_email_marketing),
                ),
                "notify_telegram_orders": _coerce_bool(
                    payload.get("notify_telegram_orders"),
                    default=bool(profile.notify_telegram_orders),
                ),
                "notify_telegram_marketing": _coerce_bool(
                    payload.get("notify_telegram_marketing"),
                    default=bool(profile.notify_telegram_marketing),
                ),
            },
            instance=profile,
        )
        if not form.is_valid():
            return JsonResponse(_validation_error_payload(form), status=400)
        profile = form.save()
        return JsonResponse({"ok": True, "preferences": _preferences_payload(profile)})


class StorefrontAccountAddressesView(View):
    """Buyer delivery-address contract for Next account."""

    @log_calls(log)
    def get(self, request):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        addresses = (
            DeliveryAddress.objects.select_related("legal_entity")
            .filter(legal_entity__members=request.user)
            .order_by("-is_default", "label")
        )
        return JsonResponse(
            {
                "ok": True,
                "addresses": [_address_payload(address) for address in addresses],
            }
        )

    @log_calls(log)
    def post(self, request):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        payload, error = _request_payload(request)
        if error:
            return _json_error(error=error, status=400)
        form = AddressForm(data=payload, user=request.user)
        if not form.is_valid():
            return JsonResponse(_validation_error_payload(form), status=400)
        address = form.save()
        return JsonResponse({"ok": True, "address": _address_payload(address)})


class StorefrontAccountAddressSetDefaultView(View):
    """Set default delivery address for the legal entity."""

    @log_calls(log)
    def post(self, request, address_id: int):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        address = (
            DeliveryAddress.objects.select_related("legal_entity")
            .filter(id=address_id, legal_entity__members=request.user)
            .first()
        )
        if not address:
            return _json_error(error="address_not_found", status=404)
        address.is_default = True
        address.save(update_fields=["is_default", "updated_at"])
        return JsonResponse({"ok": True, "address": _address_payload(address)})


class StorefrontAccountAddressDeleteView(View):
    """Delete buyer delivery address."""

    @log_calls(log)
    def post(self, request, address_id: int):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        address = DeliveryAddress.objects.filter(id=address_id, legal_entity__members=request.user).first()
        if not address:
            return _json_error(error="address_not_found", status=404)
        address.delete()
        return JsonResponse({"ok": True})


class StorefrontAccountLegalEntitiesView(View):
    """Legal entities and company workspace summary for buyer account."""

    @log_calls(log)
    def get(self, request):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        memberships = list(
            LegalEntityMembership.objects.select_related("legal_entity", "role")
            .filter(user=request.user)
            .order_by("legal_entity__name")
        )
        workspace_rows = _company_workspace_rows(request.user, memberships)
        requests_rows = (
            LegalEntityCreationRequest.objects.select_related("status")
            .filter(applicant=request.user)
            .order_by("-id")[:30]
        )
        return JsonResponse(
            {
                "ok": True,
                "memberships": [
                    {
                        "id": membership.id,
                        "legal_entity": {
                            "id": membership.legal_entity_id,
                            "name": membership.legal_entity.name,
                            "inn": membership.legal_entity.inn,
                            "bik": membership.legal_entity.bik,
                            "checking_account": membership.legal_entity.checking_account,
                            "bank_name": membership.legal_entity.bank_name or "",
                        },
                        "role": {
                            "code": getattr(membership.role, "code", "") if membership.role_id else "",
                            "name": getattr(membership.role, "name", "") if membership.role_id else "",
                        },
                    }
                    for membership in memberships
                ],
                "company_workspaces": [
                    {
                        "company_id": row["company"].id,
                        "display_name": row["company"].display_name or row["company"].legal_entity.name,
                        "legal_entity_id": row["legal_membership"].legal_entity_id,
                        "membership_role": row["membership"].role if row["membership"] else "",
                        "approval_policy": {
                            "enabled": bool(row["policy"] and row["policy"].is_enabled),
                            "auto_approve_below": _money(row["policy"].auto_approve_below if row["policy"] else Decimal("0.00")),
                            "required_approvals_count": int(row["policy"].required_approvals_count) if row["policy"] else 1,
                            "require_comment": bool(row["policy"] and row["policy"].require_comment),
                        },
                    }
                    for row in workspace_rows
                ],
                "creation_requests": [
                    {
                        "id": legal_request.id,
                        "name": legal_request.name,
                        "inn": legal_request.inn,
                        "bik": legal_request.bik,
                        "checking_account": legal_request.checking_account,
                        "bank_name": legal_request.bank_name or "",
                        "status": {
                            "code": getattr(legal_request.status, "code", "") if legal_request.status_id else "",
                            "name": getattr(legal_request.status, "name", "") if legal_request.status_id else "",
                        },
                        "created_at": legal_request.created_at.isoformat(),
                    }
                    for legal_request in requests_rows
                ],
            }
        )


class StorefrontAccountNotificationsView(View):
    """Notifications feed contract for Next buyer account."""

    @log_calls(log)
    def get(self, request):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))
        events = _notification_feed(request.user, limit=120)
        return JsonResponse(
            {
                "ok": True,
                "notifications": [
                    {
                        "at": row["at"].isoformat(),
                        "title": row["title"],
                        "subtitle": row["subtitle"],
                        "href": row["href"],
                    }
                    for row in events
                ],
            }
        )


class StorefrontAccountBootstrapView(View):
    """Buyer account dashboard bootstrap for Next storefront shell."""

    @log_calls(log)
    def get(self, request):
        if not request.user.is_authenticated:
            return _json_error(error="authentication_required", status=401, login_url=_login_url(request))

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        entity_ids = list(LegalEntityMembership.objects.filter(user=request.user).values_list("legal_entity_id", flat=True))
        recent_orders = (
            Order.objects.filter(placed_by=request.user)
            .select_related("legal_entity")
            .order_by("-created_at", "-id")[:8]
        )
        unpaid_orders = (
            Order.objects.filter(
                placed_by=request.user,
                payment_method__in=[Order.PaymentMethod.INVOICE, Order.PaymentMethod.MIR_CARD, Order.PaymentMethod.ONLINE_CARD],
                status__in=[Order.Status.NEW, Order.Status.CONFIRMED, Order.Status.CHANGED],
            )
            .select_related("legal_entity")
            .order_by("-created_at", "-id")[:8]
        )

        response = JsonResponse(
            {
                "ok": True,
                "user": _auth_user_payload(request.user),
                "profile": {
                    "id": profile.id,
                    "photo_url": profile.photo.url if profile.photo else "",
                    "role": profile.role,
                },
                "metrics": {
                    "orders_count": int(Order.objects.filter(placed_by=request.user).count()),
                    "favorites_count": int(FavoriteProduct.objects.filter(user=request.user).count()),
                    "saved_searches_count": int(SavedSearch.objects.filter(user=request.user).count()),
                    "entities_count": len(entity_ids),
                    "addresses_count": int(DeliveryAddress.objects.filter(legal_entity_id__in=entity_ids).count()),
                },
                "queues": {
                    "recent_orders": [_order_short_payload(order) for order in recent_orders],
                    "unpaid_orders": [_order_short_payload(order) for order in unpaid_orders],
                },
                "links": {
                    "orders": "/account/orders/",
                    "addresses": "/account/addresses/",
                    "legal": "/account/legal/",
                    "notifications": "/account/notifications/",
                    "preferences": "/account/preferences/",
                },
            }
        )
        response["Cache-Control"] = "no-store"
        response["Vary"] = "Cookie"
        return response
