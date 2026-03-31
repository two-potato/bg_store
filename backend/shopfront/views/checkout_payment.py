"""Payment and guest-order views for the shopfront checkout flow."""

from __future__ import annotations

from django.db.models import Prefetch
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import TemplateView

from catalog.models import ProductImage
from core.logging_utils import log_calls
from orders.models import FakeAcquiringPayment, Order, OrderItem

from ..checkout_common import log
from ..searching.attribution import order_search_attribution
from ..checkout_support import (
    allowed_fake_payment_events as _get_allowed_fake_payment_events,
    apply_fake_payment_event as _apply_fake_payment_event,
    demo_payments_enabled as _demo_payments_enabled,
    fake_payment_event_url as _fake_payment_event_url,
    fake_payment_page_url as _fake_payment_page_url,
    has_guest_order_access as _has_guest_order_access,
    online_payment_event_url as _online_payment_event_url,
    online_payment_page_url as _online_payment_page_url,
    order_detail_url as _order_detail_url,
    payment_page_context as _payment_page_context,
    remember_guest_order as _remember_guest_order,
    render_payment_panel_response as _render_payment_panel_response,
)


class FakePaymentPageView(TemplateView):
    template_name = "shopfront/fake_payment.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        if not _demo_payments_enabled():
            raise Http404("Payment page unavailable")
        order = get_object_or_404(Order.objects.select_related("placed_by"), pk=kwargs["order_id"], placed_by=request.user)
        payment = get_object_or_404(FakeAcquiringPayment, order=order)
        return render(request, self.template_name, _payment_page_context(order, payment, event_url=_fake_payment_event_url(order), search_attribution=order_search_attribution(request, order)))


class FakePaymentEventView(View):
    @log_calls(log)
    def post(self, request, order_id):
        if not _demo_payments_enabled():
            raise Http404("Payment event unavailable")
        order = get_object_or_404(Order.objects.select_related("placed_by"), pk=order_id, placed_by=request.user)
        payment = get_object_or_404(FakeAcquiringPayment, order=order)
        event = (request.POST.get("event") or "").strip()
        if event not in _get_allowed_fake_payment_events():
            return HttpResponse("Unknown event", status=400)
        _apply_fake_payment_event(order, payment, event)
        payment.refresh_from_db()
        order.refresh_from_db()
        return _render_payment_panel_response(
            request,
            order=order,
            payment=payment,
            event=event,
            event_url=_fake_payment_event_url(order),
            page_url=_fake_payment_page_url(order),
            search_attribution=order_search_attribution(request, order),
        )


class OnlinePaymentPageView(TemplateView):
    template_name = "shopfront/fake_payment.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        if not _demo_payments_enabled():
            raise Http404("Payment page unavailable")
        order = get_object_or_404(Order.objects.select_related("placed_by"), pk=kwargs["order_id"], placed_by=request.user)
        payment = get_object_or_404(FakeAcquiringPayment, order=order)
        return render(request, self.template_name, _payment_page_context(order, payment, event_url=_online_payment_event_url(order), search_attribution=order_search_attribution(request, order)))


class OnlinePaymentEventView(View):
    @log_calls(log)
    def post(self, request, order_id):
        if not _demo_payments_enabled():
            raise Http404("Payment event unavailable")
        order = get_object_or_404(Order.objects.select_related("placed_by"), pk=order_id, placed_by=request.user)
        payment = get_object_or_404(FakeAcquiringPayment, order=order)
        event = (request.POST.get("event") or "").strip()
        if event not in _get_allowed_fake_payment_events():
            return HttpResponse("Unknown event", status=400)
        _apply_fake_payment_event(order, payment, event)
        payment.refresh_from_db()
        order.refresh_from_db()
        return _render_payment_panel_response(
            request,
            order=order,
            payment=payment,
            event=event,
            event_url=_online_payment_event_url(order),
            page_url=_online_payment_page_url(order),
            search_attribution=order_search_attribution(request, order),
        )


class GuestOrderDetailView(TemplateView):
    template_name = "shopfront/guest_order_detail.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        order = get_object_or_404(
            Order.objects.select_related("legal_entity", "delivery_address", "placed_by").prefetch_related(
                Prefetch(
                    "items",
                    queryset=OrderItem.objects.select_related("product", "seller_offer").prefetch_related(
                        Prefetch(
                            "product__images",
                            queryset=ProductImage.objects.only("id", "product_id", "url", "alt", "ordering").order_by("ordering", "id"),
                            to_attr="prefetched_images",
                        )
                    ),
                ),
                "seller_splits",
                "seller_orders",
                "seller_orders__items",
                "seller_orders__items__product",
                "seller_orders__items__seller_offer",
                "seller_orders__shipments",
                "seller_orders__shipments__items",
            ),
            pk=kwargs["order_id"],
        )
        token = (kwargs.get("token") or "").strip()
        if not _has_guest_order_access(request, order, token=token):
            raise Http404("Order not found")
        if order.is_guest:
            _remember_guest_order(request, order)
        return render(
            request,
            self.template_name,
            {
                "order": order,
                "fake_payment": getattr(order, "fake_payment", None),
                "order_detail_url": _order_detail_url(order),
                "payment_page_url": (
                    _online_payment_page_url(order) if order.payment_method == Order.PaymentMethod.ONLINE_CARD else _fake_payment_page_url(order)
                ) if _demo_payments_enabled() else "",
                "demo_payments_enabled": _demo_payments_enabled(),
            },
        )


class GuestFakePaymentPageView(TemplateView):
    template_name = "shopfront/fake_payment.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        if not _demo_payments_enabled():
            raise Http404("Payment page unavailable")
        order = get_object_or_404(Order.objects.select_related("placed_by"), pk=kwargs["order_id"])
        token = (kwargs.get("token") or "").strip()
        if not _has_guest_order_access(request, order, token=token):
            raise Http404("Order not found")
        payment = get_object_or_404(FakeAcquiringPayment, order=order)
        if order.is_guest:
            _remember_guest_order(request, order)
        return render(request, self.template_name, _payment_page_context(order, payment, event_url=_fake_payment_event_url(order), search_attribution=order_search_attribution(request, order)))


class GuestFakePaymentEventView(View):
    @log_calls(log)
    def post(self, request, order_id, token):
        if not _demo_payments_enabled():
            raise Http404("Payment event unavailable")
        order = get_object_or_404(Order.objects.select_related("placed_by"), pk=order_id)
        if not _has_guest_order_access(request, order, token=(token or "").strip()):
            raise Http404("Order not found")
        payment = get_object_or_404(FakeAcquiringPayment, order=order)
        event = (request.POST.get("event") or "").strip()
        if event not in _get_allowed_fake_payment_events():
            return HttpResponse("Unknown event", status=400)
        _apply_fake_payment_event(order, payment, event)
        payment.refresh_from_db()
        order.refresh_from_db()
        return _render_payment_panel_response(
            request,
            order=order,
            payment=payment,
            event=event,
            event_url=_fake_payment_event_url(order),
            page_url=_fake_payment_page_url(order),
            search_attribution=order_search_attribution(request, order),
        )


class GuestOnlinePaymentPageView(TemplateView):
    template_name = "shopfront/fake_payment.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        if not _demo_payments_enabled():
            raise Http404("Payment page unavailable")
        order = get_object_or_404(Order.objects.select_related("placed_by"), pk=kwargs["order_id"])
        token = (kwargs.get("token") or "").strip()
        if not _has_guest_order_access(request, order, token=token):
            raise Http404("Order not found")
        payment = get_object_or_404(FakeAcquiringPayment, order=order)
        return render(request, self.template_name, _payment_page_context(order, payment, event_url=_online_payment_event_url(order), search_attribution=order_search_attribution(request, order)))


class GuestOnlinePaymentEventView(View):
    @log_calls(log)
    def post(self, request, order_id, token):
        if not _demo_payments_enabled():
            raise Http404("Payment event unavailable")
        order = get_object_or_404(Order.objects.select_related("placed_by"), pk=order_id)
        if not _has_guest_order_access(request, order, token=(token or "").strip()):
            raise Http404("Order not found")
        payment = get_object_or_404(FakeAcquiringPayment, order=order)
        event = (request.POST.get("event") or "").strip()
        if event not in _get_allowed_fake_payment_events():
            return HttpResponse("Unknown event", status=400)
        _apply_fake_payment_event(order, payment, event)
        payment.refresh_from_db()
        order.refresh_from_db()
        return _render_payment_panel_response(
            request,
            order=order,
            payment=payment,
            event=event,
            event_url=_online_payment_event_url(order),
            page_url=_online_payment_page_url(order),
            search_attribution=order_search_attribution(request, order),
        )
