from __future__ import annotations

import hmac
import json
import logging
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django_fsm import TransitionNotAllowed

from catalog.models import Product
from catalog.offer_service import resolve_product_offer
from orders.models import FakeAcquiringPayment, Order

from .checkout_flow_service import fake_payment_template_context

log = logging.getLogger("shopfront")


def new_guest_access_token() -> str:
    """Handle new guest access token."""
    return uuid4().hex


def demo_payments_enabled() -> bool:
    """Handle demo payments enabled."""
    return bool(getattr(settings, "ENABLE_DEMO_PAYMENTS", settings.DEBUG))


def allowed_payment_methods() -> tuple[str, ...]:
    """Handle allowed payment methods."""
    methods = [Order.PaymentMethod.CASH, Order.PaymentMethod.INVOICE]
    if demo_payments_enabled():
        methods.extend([Order.PaymentMethod.MIR_CARD, Order.PaymentMethod.ONLINE_CARD])
    return tuple(methods)


def guest_order_session_map(request) -> dict[str, str]:
    """Handle guest order session map."""
    raw = request.session.get("guest_order_tokens", {}) or {}
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items() if key and value}
    return {}


def remember_guest_order(request, order: Order) -> None:
    """Remember guest order."""
    token = order.guest_access_token or ""
    if not token:
        return
    payload = guest_order_session_map(request)
    payload[str(order.id)] = token
    request.session["guest_order_tokens"] = payload
    request.session.modified = True


def has_guest_order_access(request, order: Order, token: str | None = None) -> bool:
    """Handle has guest order access."""
    if request.user.is_authenticated and order.placed_by_id and order.placed_by_id == request.user.id:
        return True
    expected = (order.guest_access_token or "").strip()
    provided = (token or "").strip()
    if expected and provided and hmac.compare_digest(expected, provided):
        return True
    session_token = guest_order_session_map(request).get(str(order.id), "")
    return bool(expected and session_token and hmac.compare_digest(session_token, expected))


def order_detail_url(order: Order) -> str:
    """Handle order detail url."""
    if order.is_guest and order.guest_access_token:
        return reverse("guest_order_detail", kwargs={"order_id": order.id, "token": order.guest_access_token})
    return f"/account/orders/{order.id}/"


def fake_payment_page_url(order: Order) -> str:
    """Handle fake payment page url."""
    if order.is_guest and order.guest_access_token:
        return reverse("guest_fake_payment_page", kwargs={"order_id": order.id, "token": order.guest_access_token})
    return reverse("fake_payment_page", kwargs={"order_id": order.id})


def fake_payment_event_url(order: Order) -> str:
    """Handle fake payment event url."""
    if order.is_guest and order.guest_access_token:
        return reverse("guest_fake_payment_event", kwargs={"order_id": order.id, "token": order.guest_access_token})
    return reverse("fake_payment_event", kwargs={"order_id": order.id})


def online_payment_page_url(order: Order) -> str:
    """Handle online payment page url."""
    if order.is_guest and order.guest_access_token:
        return reverse("guest_online_payment_page", kwargs={"order_id": order.id, "token": order.guest_access_token})
    return reverse("online_payment_page", kwargs={"order_id": order.id})


def online_payment_event_url(order: Order) -> str:
    """Handle online payment event url."""
    if order.is_guest and order.guest_access_token:
        return reverse("guest_online_payment_event", kwargs={"order_id": order.id, "token": order.guest_access_token})
    return reverse("online_payment_event", kwargs={"order_id": order.id})


def tracking_item_from_product(product: Product, quantity: int = 1) -> dict:
    """Handle tracking item from product."""
    category_name = getattr(product.category, "name", "") or ""
    seller_store = getattr(getattr(product, "seller", None), "seller_store", None)
    offer = getattr(product, "active_offer", None) or resolve_product_offer(product)
    seller_store = getattr(offer, "seller_store", None) or seller_store
    price = getattr(product, "display_price", None) or getattr(offer, "price", None) or product.price
    return {
        "item_id": product.sku or str(product.id),
        "item_name": product.name,
        "item_brand": getattr(product.brand, "name", "") or "",
        "item_category": category_name,
        "item_variant": getattr(getattr(product, "series", None), "name", "") or "",
        "item_seller": getattr(seller_store, "name", "") or "",
        "price": float(Decimal(str(price)).quantize(Decimal("0.01"))),
        "quantity": max(1, int(quantity or 1)),
    }


def recommendation_impression_payload(source: str, products) -> str:
    """Handle recommendation impression payload."""
    if not products:
        return ""
    return json.dumps(
        {
            "event": "recommendation_impression",
            "recommendation_source": source,
            "ecommerce": {
                "item_list_name": source,
                "items": [tracking_item_from_product(product) for product in products[:12]],
            },
        },
        ensure_ascii=False,
    )


def checkout_items_payload(items, total: Decimal, seller_count: int) -> dict:
    """Handle checkout items payload."""
    return {
        "seller_count": seller_count,
        "ecommerce": {
            "currency": "RUB",
            "value": float(total),
            "items": [tracking_item_from_product(item["p"], quantity=item["qty"]) for item in items],
        },
    }


def checkout_step_tracking_payload(step_name: str, *, items, total: Decimal, seller_count: int) -> dict:
    """Handle checkout step tracking payload."""
    return {
        "event": "checkout_step_view",
        "checkout_step": step_name,
        **checkout_items_payload(items, total, seller_count),
    }


def checkout_error_tracking_payload(
    reason: str,
    *,
    customer_type: str = "",
    payment_method: str = "",
    items=None,
    total: Decimal = Decimal("0.00"),
    seller_count: int = 0,
) -> dict:
    """Handle checkout error tracking payload."""
    payload = {
        "event": "checkout_error",
        "checkout_step": "details",
        "error_message": reason,
        "customer_type": customer_type or "",
        "payment_method": payment_method or "",
    }
    if items:
        payload.update(checkout_items_payload(items, total, seller_count))
    return payload


def payment_tracking_payload(
    event_name: str,
    order: Order,
    payment: FakeAcquiringPayment | None = None,
    *,
    payment_event: str = "",
    search_attribution: dict | None = None,
    recommendation_attribution: dict | None = None,
) -> dict:
    """Handle payment tracking payload."""
    payload = {
        "event": event_name,
        "payment_method": order.payment_method,
        "checkout_step": "payment",
        "order_id": str(order.id),
        "customer_type": order.customer_type,
        "seller_count": order.seller_splits.count(),
        "source_channel": order.source_channel,
        "ecommerce": {
            "transaction_id": str(order.id),
            "currency": "RUB",
            "value": float(order.total),
            "items": [
                tracking_item_from_product(item.product, quantity=item.qty)
                for item in order.items.select_related(
                    "product",
                    "product__brand",
                    "product__category",
                    "product__series",
                    "product__seller",
                    "product__seller__seller_store",
                )
            ],
        },
    }
    if search_attribution:
        payload["search_attribution"] = search_attribution
    if recommendation_attribution:
        payload["recommendation_attribution"] = recommendation_attribution
    if payment is not None:
        payload["payment_status"] = payment.status
        payload["provider_payment_id"] = payment.provider_payment_id
    if payment_event:
        payload["payment_event"] = payment_event
    return payload


def order_tracking_payload(order: Order, *, search_attribution: dict | None = None, recommendation_attribution: dict | None = None) -> dict:
    """Handle order tracking payload."""
    payload = {
        "event": "purchase",
        "seller_count": order.seller_splits.count(),
        "coupon": order.coupon_code or "",
        "source_channel": order.source_channel,
        "ecommerce": {
            "transaction_id": str(order.id),
            "currency": "RUB",
            "value": float(order.total),
            "discount": float(order.discount_amount),
            "items": [
                tracking_item_from_product(item.product, quantity=item.qty)
                for item in order.items.select_related(
                    "product",
                    "product__brand",
                    "product__category",
                    "product__series",
                    "product__seller",
                    "product__seller__seller_store",
                )
            ],
        },
    }
    if search_attribution:
        payload["search_attribution"] = search_attribution
    if recommendation_attribution:
        payload["recommendation_attribution"] = recommendation_attribution
    return payload


def payment_event_label(event_code: str) -> str:
    """Handle payment event label."""
    return dict(FakeAcquiringPayment.Event.choices).get(event_code, event_code)


def allowed_fake_payment_events() -> set[str]:
    """Handle allowed fake payment events."""
    return {code for code, _ in FakeAcquiringPayment.Event.choices}


def append_payment_history(payment: FakeAcquiringPayment, event_code: str, status_code: str, note: str = ""):
    """Handle append payment history."""
    history = list(payment.history or [])
    history.append(
        {
            "at": payment.updated_at.strftime("%d.%m.%Y %H:%M:%S"),
            "event": event_code,
            "event_label": payment_event_label(event_code),
            "status": status_code,
            "status_label": dict(FakeAcquiringPayment.Status.choices).get(status_code, status_code),
            "note": note,
        }
    )
    payment.history = history[-50:]
    payment.last_event = event_code
    payment.status = status_code


def apply_fake_payment_event(order: Order, payment: FakeAcquiringPayment, event_code: str):
    """Apply fake payment event."""
    status_map = {
        FakeAcquiringPayment.Event.START: FakeAcquiringPayment.Status.PROCESSING,
        FakeAcquiringPayment.Event.REQUIRE_3DS: FakeAcquiringPayment.Status.REQUIRES_3DS,
        FakeAcquiringPayment.Event.PASS_3DS: FakeAcquiringPayment.Status.PAID,
        FakeAcquiringPayment.Event.SUCCESS: FakeAcquiringPayment.Status.PAID,
        FakeAcquiringPayment.Event.FAIL: FakeAcquiringPayment.Status.FAILED,
        FakeAcquiringPayment.Event.CANCEL: FakeAcquiringPayment.Status.CANCELED,
        FakeAcquiringPayment.Event.REFUND: FakeAcquiringPayment.Status.REFUNDED,
    }
    next_status = status_map.get(event_code)
    if not next_status:
        return
    append_payment_history(payment, event_code, next_status)
    payment.save(update_fields=["history", "last_event", "status", "updated_at"])

    if next_status == FakeAcquiringPayment.Status.PAID:
        if order.status in {Order.Status.NEW, Order.Status.CHANGED}:
            try:
                order.approve()
            except TransitionNotAllowed:
                log.warning(
                    "order_transition_fallback",
                    extra={
                        "order_id": order.id,
                        "event_code": event_code,
                        "from_status": order.status,
                        "target_status": Order.Status.CONFIRMED,
                        "transition": "approve",
                    },
                )
                order.status = Order.Status.CONFIRMED
            order.save(update_fields=["status"])
        if order.status == Order.Status.CONFIRMED:
            try:
                order.pay()
            except TransitionNotAllowed:
                log.warning(
                    "order_transition_fallback",
                    extra={
                        "order_id": order.id,
                        "event_code": event_code,
                        "from_status": order.status,
                        "target_status": Order.Status.PAID,
                        "transition": "pay",
                    },
                )
                order.status = Order.Status.PAID
            order.save(update_fields=["status"])
    elif next_status in {FakeAcquiringPayment.Status.FAILED, FakeAcquiringPayment.Status.CANCELED}:
        if order.status not in {Order.Status.CANCELED, Order.Status.DELIVERED}:
            try:
                order.cancel()
            except TransitionNotAllowed:
                log.warning(
                    "order_transition_fallback",
                    extra={
                        "order_id": order.id,
                        "event_code": event_code,
                        "from_status": order.status,
                        "target_status": Order.Status.CANCELED,
                        "transition": "cancel",
                    },
                )
                order.status = Order.Status.CANCELED
            order.save(update_fields=["status"])
    elif next_status == FakeAcquiringPayment.Status.REFUNDED:
        if order.status not in {Order.Status.CANCELED, Order.Status.DELIVERED}:
            try:
                order.mark_changed()
            except TransitionNotAllowed:
                log.warning(
                    "order_transition_fallback",
                    extra={
                        "order_id": order.id,
                        "event_code": event_code,
                        "from_status": order.status,
                        "target_status": Order.Status.CHANGED,
                        "transition": "mark_changed",
                    },
                )
                order.status = Order.Status.CHANGED
            order.save(update_fields=["status"])


def payment_mode_title(payment_method: str) -> str:
    """Handle payment mode title."""
    return "Онлайн-эквайринг" if payment_method == Order.PaymentMethod.ONLINE_CARD else "Тестовый эквайринг"


def payment_page_context(order: Order, payment: FakeAcquiringPayment, *, event_url: str, search_attribution: dict | None = None) -> dict:
    """Handle payment page context."""
    context = fake_payment_template_context(
        order=order,
        payment=payment,
        order_detail_url=order_detail_url(order),
        payment_event_url=event_url,
        payment_started_tracking_payload=json.dumps(
            payment_tracking_payload("payment_started", order, payment, payment_event=payment.last_event, search_attribution=search_attribution),
            ensure_ascii=False,
        ),
    )
    if order.payment_method == Order.PaymentMethod.ONLINE_CARD:
        context["payment_mode_title"] = payment_mode_title(order.payment_method)
    return context


def payment_panel_context(order: Order, payment: FakeAcquiringPayment, *, event_url: str, page_url: str) -> dict:
    """Handle payment panel context."""
    context = fake_payment_template_context(
        order=order,
        payment=payment,
        order_detail_url=order_detail_url(order),
        payment_event_url=event_url,
        payment_page_url=page_url,
    )
    if order.payment_method == Order.PaymentMethod.ONLINE_CARD:
        context["payment_mode_title"] = payment_mode_title(order.payment_method)
    return context


def payment_event_trigger_payload(order: Order, payment: FakeAcquiringPayment, event: str, *, search_attribution: dict | None = None) -> dict:
    """Handle payment event trigger payload."""
    payload = {
        "toast": {
            "message": f"Событие: {payment_event_label(event)}",
            "variant": "success" if payment.status == FakeAcquiringPayment.Status.PAID else "warning",
        }
    }
    if payment.status == FakeAcquiringPayment.Status.PAID:
        payload["analyticsEvent"] = order_tracking_payload(order, search_attribution=search_attribution)
    elif event in {FakeAcquiringPayment.Event.FAIL, FakeAcquiringPayment.Event.CANCEL}:
        payload["analyticsEvent"] = payment_tracking_payload("payment_failed", order, payment, payment_event=event, search_attribution=search_attribution)
    return payload


def render_payment_panel_response(
    request,
    *,
    order: Order,
    payment: FakeAcquiringPayment,
    event: str,
    event_url: str,
    page_url: str,
    search_attribution: dict | None = None,
) -> HttpResponse:
    """Render payment panel response."""
    response = HttpResponse(
        render_to_string(
            "shopfront/partials/fake_payment_panel.html",
            payment_panel_context(order, payment, event_url=event_url, page_url=page_url),
            request=request,
        )
    )
    response["HX-Trigger"] = json.dumps(payment_event_trigger_payload(order, payment, event, search_attribution=search_attribution))
    return response
