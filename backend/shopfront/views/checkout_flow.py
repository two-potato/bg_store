"""Checkout page and submit orchestration views."""

from __future__ import annotations

import json

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView

from core.logging_utils import log_calls

from ..checkout_orchestration_service import CheckoutSubmissionService
from ..checkout_support import (
    checkout_items_payload as _checkout_items_payload,
    order_detail_url as _order_detail_url,
    payment_panel_context as _payment_panel_context,
)
from ..checkout_common import build_checkout_context as _checkout_context, log, seo_context as _seo_context
from ..recommendation.service import checkout_recommendations


def _checkout_success_response(request, *, is_hx: bool, message: str, redirect_to: str):
    messages.success(request, message)
    if is_hx:
        response = HttpResponse(
            f'<div class="hidden" data-checkout-redirect="{redirect_to}">{redirect_to}</div>',
            status=200,
        )
        response["HX-Redirect"] = redirect_to
        return response
    return redirect(redirect_to)


def _checkout_failure_response(request, *, is_hx: bool, message: str):
    if is_hx:
        ctx = _checkout_context(request, form_data=request.POST, checkout_error=message)
        return render(request, "shopfront/partials/checkout_form_panel.html", ctx, status=422)
    messages.error(request, message)
    return redirect("checkout")


class CheckoutPageView(TemplateView):
    template_name = "shopfront/checkout.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_checkout_context(self.request))
        rec_ctx = checkout_recommendations(
            [item["p"] for item in ctx.get("items", [])],
            user=self.request.user,
            request=self.request,
            limit=6,
        )
        ctx["checkout_recommendations"] = rec_ctx["products"]
        ctx["checkout_recommendations_tracking_payload"] = rec_ctx["tracking_payload"]
        ctx["begin_checkout_tracking_payload"] = (
            json.dumps(
                {
                    "event": "begin_checkout",
                    **_checkout_items_payload(
                        ctx["items"],
                        ctx["total"],
                        ctx["seller_count"],
                    ),
                },
                ensure_ascii=False,
            )
            if ctx["items"]
            else ""
        )
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
        result = CheckoutSubmissionService(request).submit()
        if result.error:
            return _checkout_failure_response(request, is_hx=is_hx, message=result.error)

        assert result.order is not None
        if result.payment_context is not None and is_hx:
            response = render(
                request,
                "shopfront/partials/fake_payment_panel.html",
                _payment_panel_context(
                    result.order,
                    result.payment_context.payment,
                    event_url=result.payment_context.event_url,
                    page_url=result.payment_context.page_url,
                ),
            )
            response["HX-Trigger"] = json.dumps(result.payment_context.trigger_payload)
            return response

        return _checkout_success_response(
            request,
            is_hx=is_hx,
            message=result.success_message,
            redirect_to=result.redirect_to or _order_detail_url(result.order),
        )
