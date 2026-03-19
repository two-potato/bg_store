"""Checkout page and submit orchestration views."""

from __future__ import annotations

import json
from uuid import uuid4

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView

from catalog.models import Product
from core.logging_utils import log_calls
from orders.models import FakeAcquiringPayment, Order, OrderItem
from orders.payment_providers import get_payment_provider
from orders.services import plan_seller_splits
from promotions.services import create_redemption, resolve_checkout_discount

from ..cart_checkout_service import session_cart as _cart
from ..checkout_common import build_checkout_context as _checkout_context, log, seo_context as _seo_context
from ..recommendation_attribution_service import (
    clear_cart_recommendation_attribution,
    order_recommendation_attribution,
    record_recommendation_event,
    remember_order_recommendation_attribution,
)
from ..recommendation_observability import observe_recommendation_order_attribution
from ..search_attribution_service import clear_cart_search_attribution, order_search_attribution, remember_order_search_attribution
from ..search_observability import observe_search_feedback_event, observe_search_order_attribution
from ..checkout_submit_service import (
    build_checkout_lines,
    build_order_items,
    create_checkout_order,
    finalize_checkout_order,
    load_checkout_products,
    parse_checkout_submission,
)
from ..checkout_support import (
    allowed_payment_methods as _allowed_payment_methods,
    append_payment_history as _append_payment_history,
    checkout_items_payload as _checkout_items_payload,
    fake_payment_event_url as _fake_payment_event_url,
    fake_payment_page_url as _fake_payment_page_url,
    new_guest_access_token as _new_guest_access_token,
    online_payment_event_url as _online_payment_event_url,
    online_payment_page_url as _online_payment_page_url,
    order_detail_url as _order_detail_url,
    payment_panel_context as _payment_panel_context,
    payment_tracking_payload as _payment_tracking_payload,
    recommendation_impression_payload as _recommendation_impression_payload,
    remember_guest_order as _remember_guest_order,
)
from ..models import PersistentCart
from ..recommendation_service import checkout_recommendations


class CheckoutPageView(TemplateView):
    template_name = "shopfront/checkout.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_checkout_context(self.request))
        rec_ctx = checkout_recommendations([item["p"] for item in ctx.get("items", [])], user=self.request.user, request=self.request, limit=6)
        ctx["checkout_recommendations"] = rec_ctx["products"]
        ctx["checkout_recommendations_tracking_payload"] = rec_ctx["tracking_payload"]
        ctx["begin_checkout_tracking_payload"] = json.dumps(
            {"event": "begin_checkout", **_checkout_items_payload(ctx["items"], ctx["total"], ctx["seller_count"])},
            ensure_ascii=False,
        ) if ctx["items"] else ""
        ctx.update(
            _seo_context(
                self.request,
                title="Оформление заказа — Servio",
                description="Оформление заказа на Servio.",
                robots="noindex,nofollow",
            )
        )
        return ctx


class CheckoutSubmitView(View):
    @log_calls(log)
    def post(self, request):
        is_hx = bool(request.headers.get("HX-Request"))

        def succeed(message, redirect_to):
            messages.success(request, message)
            if is_hx:
                response = HttpResponse(f'<div class="hidden" data-checkout-redirect="{redirect_to}">{redirect_to}</div>', status=200)
                response["HX-Redirect"] = redirect_to
                return response
            return redirect(redirect_to)

        def fail(msg):
            if is_hx:
                ctx = _checkout_context(request, form_data=request.POST, checkout_error=msg)
                return render(request, "shopfront/partials/checkout_form_panel.html", ctx, status=422)
            messages.error(request, msg)
            return redirect("checkout")

        from core.models import IdempotencyKey

        idem_key = request.headers.get("X-Idempotency-Key") or request.POST.get("_idem")
        user_id = request.user.id if request.user.is_authenticated else 0
        if idem_key:
            key_obj, created = IdempotencyKey.create_or_get(user_id=user_id, route="checkout_submit", key=idem_key, ttl_sec=600)
            if not created:
                if is_hx:
                    return fail("Заказ уже оформлен")
                messages.info(request, "Заказ уже оформлен")
                return redirect("checkout")
        submission, submission_error = parse_checkout_submission(request, allowed_payment_methods=_allowed_payment_methods())
        if submission_error:
            return fail(submission_error)
        assert submission is not None
        cart = _cart(request)
        if not cart:
            return fail("Корзина пуста")
        products = load_checkout_products(cart)
        if not products:
            return fail("Товары не найдены")
        checkout_lines, checkout_lines_error = build_checkout_lines(cart, products)
        if checkout_lines_error:
            return fail(checkout_lines_error)
        with transaction.atomic():
            discount_result = resolve_checkout_discount(
                user=request.user,
                customer_type=submission.customer_type,
                coupon_code=submission.coupon_code,
                guest_email=submission.guest_email,
                lines=checkout_lines,
                lock=True,
            )
            if discount_result.error:
                return fail(discount_result.error)
            order, order_error = create_checkout_order(
                request=request,
                submission=submission,
                discount_result=discount_result,
                new_guest_access_token=_new_guest_access_token,
            )
            if order_error:
                return fail(order_error)
            assert order is not None
            OrderItem.objects.bulk_create(build_order_items(cart=cart, products=products, order=order))
            finalize_checkout_order(order=order, submission=submission, request_user=request.user, discount_result=discount_result)
            create_redemption(order=order, discount_result=discount_result, user=request.user, guest_email=submission.guest_email)
            plan_seller_splits(order)
        order_attribution = order_search_attribution(request, order)
        remember_order_search_attribution(request, order=order, attribution=order_attribution)
        recommendation_attribution = order_recommendation_attribution(request, order)
        remember_order_recommendation_attribution(request, order=order, attribution=recommendation_attribution)
        if order_attribution:
            observe_search_order_attribution(order=order, attribution=order_attribution, logger=log)
            for item in order_attribution.get("items", []):
                observe_search_feedback_event(
                    event_name="purchase",
                    surface="checkout",
                    origin=item.get("search_origin", "unknown"),
                    search_term=item.get("search_term", ""),
                    item_id=item.get("product_id", ""),
                    item_name=item.get("product_name", ""),
                    position=int(item.get("position") or 0),
                    results_count=0,
                    provider=item.get("search_provider", ""),
                    rewrite_kind=item.get("search_rewrite_kind", ""),
                    logger=log,
                )
        if recommendation_attribution:
            observe_recommendation_order_attribution(order=order, attribution=recommendation_attribution, logger=log)
            for item in recommendation_attribution.get("items", []):
                product = next((order_item.product for order_item in order.items.all() if str(order_item.product_id) == str(item.get("product_id"))), None)
                if product is None:
                    continue
                record_recommendation_event(
                    request=request,
                    event_name="purchase",
                    product=product,
                    attribution=item,
                    payload={"surface": "checkout", "order_id": order.id},
                    logger=log,
                )
        request.session["cart"] = {}
        clear_cart_search_attribution(request)
        clear_cart_recommendation_attribution(request)
        request.session["checkout_idem_key"] = uuid4().hex
        request.session.modified = True
        if order.is_guest:
            _remember_guest_order(request, order)
        elif request.user.is_authenticated:
            PersistentCart.objects.update_or_create(user=request.user, defaults={"payload": {}})
        if submission.payment_method in {Order.PaymentMethod.MIR_CARD, Order.PaymentMethod.ONLINE_CARD}:
            provider = get_payment_provider(submission.payment_method)
            provider_result = provider.initialize(order) if provider else None
            payment = provider_result.payment if provider_result else FakeAcquiringPayment.objects.get(order=order)
            if not payment.history:
                _append_payment_history(payment, FakeAcquiringPayment.Event.START, FakeAcquiringPayment.Status.PROCESSING, note="Симуляция эквайринга запущена")
                payment.save(update_fields=["history", "status", "last_event", "updated_at"])
            if is_hx:
                resp = render(
                    request,
                    "shopfront/partials/fake_payment_panel.html",
                    _payment_panel_context(
                        order,
                        payment,
                        event_url=_online_payment_event_url(order) if submission.payment_method == Order.PaymentMethod.ONLINE_CARD else _fake_payment_event_url(order),
                        page_url=_online_payment_page_url(order) if submission.payment_method == Order.PaymentMethod.ONLINE_CARD else _fake_payment_page_url(order),
                    ),
                )
                resp["HX-Trigger"] = json.dumps(
                    {
                        "showToast": {"message": f"Заказ #{order.id} создан. Платёж инициализирован", "variant": "success"},
                        "cartChanged": {},
                        "analyticsEvent": _payment_tracking_payload(
                            "payment_started",
                            order,
                            payment,
                            payment_event=FakeAcquiringPayment.Event.START,
                            search_attribution=order_attribution,
                        ),
                    }
                )
                return resp
            return succeed(f"Заказ #{order.id} создан. Можно перейти к оплате.", _order_detail_url(order))
        return succeed(f"Заказ #{order.id} создан", _order_detail_url(order))
