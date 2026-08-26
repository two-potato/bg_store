"""Service layer for checkout submission orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from django.db import transaction

from core.logging_utils import log_calls
from orders.models import FakeAcquiringPayment, Order, OrderItem
from orders.payment_providers import get_payment_provider
from orders.services import plan_seller_splits
from promotions.services import create_redemption, resolve_checkout_discount

from .cart_checkout_service import session_cart as _cart
from .checkout_submit_service import (
    build_checkout_lines,
    build_order_items,
    create_checkout_order,
    finalize_checkout_order,
    load_checkout_products,
    parse_checkout_submission,
)
from .checkout_support import (
    allowed_payment_methods as _allowed_payment_methods,
    append_payment_history as _append_payment_history,
    fake_payment_event_url as _fake_payment_event_url,
    fake_payment_page_url as _fake_payment_page_url,
    new_guest_access_token as _new_guest_access_token,
    online_payment_event_url as _online_payment_event_url,
    online_payment_page_url as _online_payment_page_url,
    order_detail_url as _order_detail_url,
    payment_tracking_payload as _payment_tracking_payload,
    remember_guest_order as _remember_guest_order,
)
from .models import PersistentCart
from .recommendation.attribution_service import (
    clear_cart_recommendation_attribution,
    order_recommendation_attribution,
    remember_order_recommendation_attribution,
)
from .searching.attribution import (
    clear_cart_search_attribution,
    order_search_attribution,
    remember_order_search_attribution,
)
from .views.constants import log


@dataclass(slots=True)
class CheckoutPaymentContext:
    """Rendered payment continuation context after a successful checkout."""

    payment: FakeAcquiringPayment
    event_url: str
    page_url: str
    trigger_payload: dict[str, Any]


@dataclass(slots=True)
class CheckoutSubmitResult:
    """Service result for checkout submission."""

    error: str | None = None
    order: Order | None = None
    redirect_to: str = ""
    success_message: str = ""
    payment_context: CheckoutPaymentContext | None = None


class CheckoutSubmissionService:
    """Orchestrate checkout submission outside the HTTP view layer."""

    def __init__(self, request) -> None:
        self.request = request

    @log_calls(log)
    def submit(self) -> CheckoutSubmitResult:
        """Validate checkout input, create the order, and initialize follow-up flows."""
        idempotency_error = self._reserve_idempotency_key()
        if idempotency_error:
            return CheckoutSubmitResult(error=idempotency_error)

        submission, submission_error = parse_checkout_submission(
            self.request,
            allowed_payment_methods=_allowed_payment_methods(),
        )
        if submission_error:
            return CheckoutSubmitResult(error=submission_error)
        assert submission is not None

        cart = _cart(self.request)
        if not cart:
            return CheckoutSubmitResult(error="Корзина пуста")
        products = load_checkout_products(cart)
        if not products:
            return CheckoutSubmitResult(error="Товары не найдены")
        checkout_lines, checkout_lines_error = build_checkout_lines(cart, products)
        if checkout_lines_error:
            return CheckoutSubmitResult(error=checkout_lines_error)

        order = self._create_order(
            submission=submission,
            cart=cart,
            products=products,
            checkout_lines=checkout_lines,
        )
        if isinstance(order, CheckoutSubmitResult):
            return order

        order_attribution = order_search_attribution(self.request, order)
        remember_order_search_attribution(self.request, order=order, attribution=order_attribution)
        recommendation_attribution = order_recommendation_attribution(self.request, order)
        remember_order_recommendation_attribution(
            self.request,
            order=order,
            attribution=recommendation_attribution,
        )
        from .tasks import (
            emit_checkout_recommendation_feedback,
            emit_checkout_search_feedback,
        )

        if order_attribution:
            transaction.on_commit(
                lambda: emit_checkout_search_feedback.delay(
                    order_id=order.id,
                    attribution=order_attribution,
                )
            )
        if recommendation_attribution:
            transaction.on_commit(
                lambda: emit_checkout_recommendation_feedback.delay(
                    order_id=order.id,
                    attribution=recommendation_attribution,
                )
            )

        self._clear_checkout_state(order)
        payment_context = self._initialize_payment(
            order=order,
            payment_method=submission.payment_method,
            order_attribution=order_attribution,
        )
        if payment_context is not None:
            return CheckoutSubmitResult(
                order=order,
                redirect_to=_order_detail_url(order),
                success_message=f"Заказ #{order.id} создан. Можно перейти к оплате.",
                payment_context=payment_context,
            )
        return CheckoutSubmitResult(
            order=order,
            redirect_to=_order_detail_url(order),
            success_message=f"Заказ #{order.id} создан",
        )

    def _reserve_idempotency_key(self) -> str | None:
        from core.models import IdempotencyKey

        idem_key = self.request.headers.get("X-Idempotency-Key") or self.request.POST.get("_idem")
        user_id = self.request.user.id if self.request.user.is_authenticated else 0
        if not idem_key:
            return None
        _, created = IdempotencyKey.create_or_get(
            user_id=user_id,
            route="checkout_submit",
            key=idem_key,
            ttl_sec=600,
        )
        if created:
            return None
        return "Заказ уже оформлен"

    def _create_order(self, *, submission, cart: dict, products: dict, checkout_lines: list[dict]) -> Order | CheckoutSubmitResult:
        with transaction.atomic():
            discount_result = resolve_checkout_discount(
                user=self.request.user,
                customer_type=submission.customer_type,
                coupon_code=submission.coupon_code,
                guest_email=submission.guest_email,
                lines=checkout_lines,
                lock=True,
            )
            if discount_result.error:
                return CheckoutSubmitResult(error=discount_result.error)

            order, order_error = create_checkout_order(
                request=self.request,
                submission=submission,
                discount_result=discount_result,
                new_guest_access_token=_new_guest_access_token,
            )
            if order_error:
                return CheckoutSubmitResult(error=order_error)
            assert order is not None

            OrderItem.objects.bulk_create(
                build_order_items(cart=cart, products=products, order=order)
            )
            finalize_checkout_order(
                order=order,
                submission=submission,
                request_user=self.request.user,
                discount_result=discount_result,
            )
            create_redemption(
                order=order,
                discount_result=discount_result,
                user=self.request.user,
                guest_email=submission.guest_email,
            )
            plan_seller_splits(order)
        return order

    def _clear_checkout_state(self, order: Order) -> None:
        self.request.session["cart"] = {}
        clear_cart_search_attribution(self.request)
        clear_cart_recommendation_attribution(self.request)
        self.request.session["checkout_idem_key"] = uuid4().hex
        self.request.session.modified = True
        if order.is_guest:
            _remember_guest_order(self.request, order)
        elif self.request.user.is_authenticated:
            PersistentCart.objects.update_or_create(
                user=self.request.user,
                defaults={"payload": {}},
            )

    def _initialize_payment(self, *, order: Order, payment_method: str, order_attribution: dict | None) -> CheckoutPaymentContext | None:
        if payment_method not in {Order.PaymentMethod.MIR_CARD, Order.PaymentMethod.ONLINE_CARD}:
            return None
        provider = get_payment_provider(payment_method)
        provider_result = provider.initialize(order) if provider else None
        payment = (
            provider_result.payment
            if provider_result
            else FakeAcquiringPayment.objects.get(order=order)
        )
        if not payment.history:
            _append_payment_history(
                payment,
                FakeAcquiringPayment.Event.START,
                FakeAcquiringPayment.Status.PROCESSING,
                note="Симуляция эквайринга запущена",
            )
            payment.save(update_fields=["history", "status", "last_event", "updated_at"])
        event_url = (
            _online_payment_event_url(order)
            if payment_method == Order.PaymentMethod.ONLINE_CARD
            else _fake_payment_event_url(order)
        )
        page_url = (
            _online_payment_page_url(order)
            if payment_method == Order.PaymentMethod.ONLINE_CARD
            else _fake_payment_page_url(order)
        )
        trigger_payload = {
            "showToast": {
                "message": f"Заказ #{order.id} создан. Платёж инициализирован",
                "variant": "success",
            },
            "cartChanged": {},
            "analyticsEvent": _payment_tracking_payload(
                "payment_started",
                order,
                payment,
                payment_event=FakeAcquiringPayment.Event.START,
                search_attribution=order_attribution,
            ),
        }
        return CheckoutPaymentContext(
            payment=payment,
            event_url=event_url,
            page_url=page_url,
            trigger_payload=trigger_payload,
        )
