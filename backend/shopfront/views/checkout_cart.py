"""Cart page, badge, panel, and mutation views for the shopfront."""

from __future__ import annotations

import json

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView

from catalog.models import Product
from core.logging_utils import log_calls

from ..cart_checkout_service import cart_badge_context as _cart_badge_context, cart_summary as _cart_summary
from ..cart_mutation_service import add_to_cart_session, clear_cart_session, remove_from_cart_session, update_cart_session
from ..checkout_common import attach_cart_badge_oob as _attach_cart_badge_oob, log, seo_context as _seo_context
from ..checkout_support import recommendation_impression_payload as _recommendation_impression_payload, tracking_item_from_product as _tracking_item_from_product
from ..recommendation_attribution_service import (
    bind_cart_item_recommendation_attribution,
    cart_item_recommendation_attribution,
    record_recommendation_event,
    remove_cart_item_recommendation_attribution,
    recommendation_attribution_for_product,
)
from ..recommendation_service import cart_recommendations
from ..search_attribution_service import bind_cart_item_search_attribution, search_attribution_for_product
from ..search_observability import observe_search_feedback_event


class CartBadgeView(TemplateView):
    template_name = "shopfront/partials/cart_badge.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        resp = render(request, self.template_name, _cart_badge_context(request))
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return resp


class CartPanelView(TemplateView):
    template_name = "shopfront/partials/cart_panel.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, _cart_summary(request))


class CartAddView(View):
    @log_calls(log)
    def post(self, request):
        try:
            pid = int(request.POST.get("product_id"))
            qty = int(request.POST.get("qty", 1))
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "error": "invalid_payload"}, status=400)
        try:
            mutation = add_to_cart_session(request=request, product_id=pid, qty=qty, logger=log)
        except Product.DoesNotExist:
            log.warning("cart_add_product_not_found", extra={"product_id": pid})
            return JsonResponse({"ok": False, "error": "product_not_found"}, status=404)
        search_attribution = search_attribution_for_product(request, pid)
        recommendation_attribution = recommendation_attribution_for_product(request, pid)
        if search_attribution:
            bind_cart_item_search_attribution(request, product_id=pid, attribution=search_attribution)
            observe_search_feedback_event(
                event_name="add_to_cart",
                surface=search_attribution.get("page_type", "unknown"),
                origin=search_attribution.get("search_origin", "unknown"),
                search_term=search_attribution.get("search_term", ""),
                item_id=str(pid),
                item_name=mutation["product"].name,
                position=int(search_attribution.get("position") or 0),
                results_count=int(search_attribution.get("results_count") or 0),
                provider=search_attribution.get("search_provider", ""),
                rewrite_kind=search_attribution.get("search_rewrite_kind", ""),
                logger=log,
            )
        if recommendation_attribution:
            bind_cart_item_recommendation_attribution(request, product_id=pid, attribution=recommendation_attribution)
            record_recommendation_event(
                request=request,
                event_name="add_to_cart",
                product=mutation["product"],
                attribution=recommendation_attribution,
                payload={"surface": "cart", "line_value": float(mutation["line_value"])},
                logger=log,
            )
        triggers = json.dumps(
            {
                "showToast": {"message": "Товар добавлен в корзину", "variant": "success"},
                "cartChanged": {},
                "cartQtyUpdated": {"product_id": pid, "qty": mutation["current_qty"]},
                "analyticsEvent": {
                    "event": "add_to_cart",
                    "search_term": search_attribution.get("search_term", ""),
                    "search_origin": search_attribution.get("search_origin", ""),
                    "search_provider": search_attribution.get("search_provider", ""),
                    "search_rewrite_kind": search_attribution.get("search_rewrite_kind", ""),
                    "recommendation_source": recommendation_attribution.get("recommendation_source", ""),
                    "recommendation_surface": recommendation_attribution.get("surface", ""),
                    "experiment_variant": recommendation_attribution.get("experiment_variant", ""),
                    "ecommerce": {
                        "currency": "RUB",
                        "value": float(mutation["line_value"]),
                        "items": [_tracking_item_from_product(mutation["product"], quantity=max(1, qty))],
                    },
                },
            }
        )
        resp = HttpResponse("", status=200)
        resp["HX-Trigger"] = triggers
        resp["HX-Trigger-After-Settle"] = triggers
        return _attach_cart_badge_oob(request, resp)


class BuyNowView(View):
    @log_calls(log)
    def post(self, request):
        try:
            pid = int(request.POST.get("product_id"))
            qty = int(request.POST.get("qty", 1))
        except (TypeError, ValueError):
            messages.error(request, "Не удалось подготовить быстрый заказ")
            return redirect("catalog")
        try:
            add_to_cart_session(request=request, product_id=pid, qty=qty, logger=log)
        except Product.DoesNotExist:
            log.warning("buy_now_product_not_found", extra={"product_id": pid})
            messages.error(request, "Товар не найден")
            return redirect("catalog")
        search_attribution = search_attribution_for_product(request, pid)
        recommendation_attribution = recommendation_attribution_for_product(request, pid)
        if search_attribution:
            bind_cart_item_search_attribution(request, product_id=pid, attribution=search_attribution)
        if recommendation_attribution:
            bind_cart_item_recommendation_attribution(request, product_id=pid, attribution=recommendation_attribution)
        return redirect("checkout")


class CartPageView(TemplateView):
    template_name = "shopfront/cart.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_cart_summary(self.request))
        rec_ctx = cart_recommendations([item["p"] for item in ctx.get("items", [])], user=self.request.user, request=self.request, limit=8)
        ctx["cart_recommendations"] = rec_ctx["products"]
        ctx["cart_recommendations_tracking_payload"] = rec_ctx["tracking_payload"]
        ctx["cart_reorder_recommendations"] = []
        if not ctx.get("items"):
            from ..recommendation_service import reorder_recommendations

            ctx["cart_reorder_recommendations"] = reorder_recommendations(self.request.user, limit=8)
        ctx.update(
            _seo_context(
                self.request,
                title="Корзина — Servio",
                description="Корзина пользователя Servio.",
                robots="noindex,nofollow",
            )
        )
        return ctx


class CartRemoveView(View):
    @log_calls(log)
    def post(self, request):
        pid = request.POST.get("product_id")
        recommendation_attribution = cart_item_recommendation_attribution(request, product_id=pid)
        product = None
        if str(pid or "").isdigit():
            product = Product.objects.filter(pk=int(pid)).first()
        remove_from_cart_session(request=request, product_id=pid)
        if product is not None and recommendation_attribution:
            record_recommendation_event(
                request=request,
                event_name="remove_from_cart",
                product=product,
                attribution=recommendation_attribution,
                payload={"surface": "cart"},
                logger=log,
            )
            remove_cart_item_recommendation_attribution(request, product_id=pid)
        cart_ctx = _cart_summary(request)
        target = (request.headers.get("HX-Target") or "").strip()
        template = "shopfront/partials/cart_content.html" if target == "cart-root" else "shopfront/partials/cart_panel.html"
        resp = render(request, template, cart_ctx)
        try:
            pid_int = int(pid)
        except (TypeError, ValueError):
            pid_int = None
        payload = {"showToast": {"message": "Удалено из корзины", "variant": "info"}, "cartChanged": {}}
        if pid_int is not None:
            payload["cartQtyUpdated"] = {"product_id": pid_int, "qty": 0}
        resp["HX-Trigger"] = json.dumps(payload)
        return _attach_cart_badge_oob(request, resp)


class CartClearView(View):
    @log_calls(log)
    def post(self, request):
        cart_products = {
            str(product_id): Product.objects.filter(pk=int(product_id)).first()
            for product_id in list((request.session.get("cart") or {}).keys())
            if str(product_id or "").isdigit()
        }
        for product_id, product in cart_products.items():
            attribution = cart_item_recommendation_attribution(request, product_id=product_id)
            if product is None or not attribution:
                continue
            record_recommendation_event(
                request=request,
                event_name="remove_from_cart",
                product=product,
                attribution=attribution,
                payload={"surface": "cart", "clear_all": True},
                logger=log,
            )
            remove_cart_item_recommendation_attribution(request, product_id=product_id)
        clear_cart_session(request=request)
        cart_ctx = _cart_summary(request)
        target = (request.headers.get("HX-Target") or "").strip()
        template = "shopfront/partials/cart_content.html" if target == "cart-root" else "shopfront/partials/cart_panel.html"
        resp = render(request, template, cart_ctx)
        resp["HX-Trigger"] = '{"showToast": {"message": "Корзина очищена", "variant": "info"}, "cartChanged": {}}'
        return _attach_cart_badge_oob(request, resp)


class CartUpdateView(View):
    @log_calls(log)
    def post(self, request):
        pid = request.POST.get("product_id")
        op = (request.POST.get("op") or "").strip()
        try:
            pid_int = int(pid)
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "error": "invalid_product"}, status=400)
        mutation = update_cart_session(
            request=request,
            product_id=pid_int,
            op=op,
            requested_qty=request.POST.get("qty", 1),
            logger=log,
        )
        if mutation["missing"]:
            return render(request, "shopfront/partials/cart_content.html", _cart_summary(request), status=404)
        cart_ctx = _cart_summary(request)
        target = (request.headers.get("HX-Target") or "").strip()
        template = "shopfront/partials/cart_content.html" if target == "cart-root" else "shopfront/partials/cart_panel.html"
        resp = render(request, template, cart_ctx)
        resp["HX-Trigger"] = json.dumps(
            {
                "showToast": {"message": "Количество обновлено", "variant": "success"},
                "cartChanged": {},
                "cartQtyUpdated": {"product_id": pid_int, "qty": mutation["qty"]},
            }
        )
        return _attach_cart_badge_oob(request, resp)
