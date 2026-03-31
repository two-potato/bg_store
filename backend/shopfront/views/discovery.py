"""Discovery, favorites, compare, and saved-list UI views."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from catalog.models import Brand, Category, Product
from core.logging_utils import log_calls
from orders.models import Order

from ..cart_checkout_service import session_cart as _cart
from ..searching.live import live_search_context
from ..models import (
    BrandSubscription,
    CategorySubscription,
    FavoriteProduct,
    SavedList,
    SavedSearch,
)
from ..recommendation.attribution_service import record_recommendation_event
from ..searching.service import get_search_provider
from ..checkout_support import tracking_item_from_product as _tracking_item_from_product
from ..view_mixins import JsonLoginRequiredMixin
from ..saved_list_service import (
    FavoriteOperationService,
    SavedListOperationService,
    SavedSearchService,
    SubscriptionOperationService,
)
from .constants import COMPARE_LIMIT, log
from .utils_seo import _absolute_url, _seo_context, _truncate_text
from .utils_state import (
    _cart_add_product,
    _compare_fields,
    _compare_ids,
    _saved_list_add_products,
    _saved_list_queryset,
    _set_compare_ids,
)
from ..catalog_selectors import (
    ordered_products_with_related as _ordered_products_with_related,
)


class FavoriteToggleView(JsonLoginRequiredMixin, LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request):
        product_id = request.POST.get("product_id")
        if not str(product_id or "").isdigit():
            log.warning(
                "favorite_toggle_invalid_payload",
                extra={
                    "ui_surface": "favorites_toggle",
                    "product_id": product_id or "",
                },
            )
            return JsonResponse(
                {"ok": False, "error": "invalid product_id"}, status=400
            )
        try:
            product = Product.objects.get(pk=int(product_id))
        except Product.DoesNotExist:
            log.warning(
                "favorite_toggle_product_not_found",
                extra={"ui_surface": "favorites_toggle", "product_id": int(product_id)},
            )
            return JsonResponse({"ok": False, "error": "product_not_found"}, status=404)
        _, created = FavoriteOperationService(request.user).toggle_favorite(
            product=product,
            request=request,
        )
        log.info(
            "favorite_toggle_ok",
            extra={
                "ui_surface": "favorites_toggle",
                "product_id": product.id,
                "favorited": created,
                "user_id": request.user.id,
            },
        )
        return JsonResponse(
            {
                "ok": True,
                "favorited": created,
                "tracking": {
                    "event": "wishlist_add" if created else "wishlist_remove",
                    "ecommerce": {"items": [_tracking_item_from_product(product)]},
                },
            }
        )


class SubscriptionToggleView(JsonLoginRequiredMixin, LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request):
        entity = (request.POST.get("entity") or "").strip()
        entity_id = request.POST.get("entity_id")
        if not str(entity_id or "").isdigit():
            log.warning(
                "subscription_toggle_invalid_entity_id",
                extra={
                    "ui_surface": "subscription_toggle",
                    "entity": entity,
                    "entity_id": entity_id or "",
                },
            )
            return JsonResponse({"ok": False, "error": "invalid entity_id"}, status=400)

        model_map = {
            "brand": (BrandSubscription, Brand, "brand"),
            "category": (CategorySubscription, Category, "category"),
        }
        if entity not in model_map:
            log.warning(
                "subscription_toggle_invalid_entity",
                extra={
                    "ui_surface": "subscription_toggle",
                    "entity": entity,
                    "entity_id": int(entity_id),
                },
            )
            return JsonResponse({"ok": False, "error": "invalid entity"}, status=400)

        _, source_model, _ = model_map[entity]
        try:
            source = source_model.objects.get(pk=int(entity_id))
        except source_model.DoesNotExist:
            log.warning(
                "subscription_toggle_source_not_found",
                extra={
                    "ui_surface": "subscription_toggle",
                    "entity": entity,
                    "entity_id": int(entity_id),
                },
            )
            return JsonResponse({"ok": False, "error": "entity_not_found"}, status=404)
        result = SubscriptionOperationService(request.user).toggle_subscription(
            entity=entity,
            entity_id=source.id,
        )
        if not result.success:
            return JsonResponse(
                {"ok": False, "error": result.message},
                status=400,
            )
        subscribed = bool((result.meta or {}).get("subscribed"))

        log.info(
            "subscription_toggle_ok",
            extra={
                "ui_surface": "subscription_toggle",
                "entity": entity,
                "entity_id": int(entity_id),
                "subscribed": subscribed,
                "user_id": request.user.id,
            },
        )

        return JsonResponse(
            {
                "ok": True,
                "subscribed": subscribed,
                "entity": entity,
                "entity_id": int(entity_id),
            }
        )


class CompareToggleView(View):
    @log_calls(log)
    def post(self, request):
        product_id = request.POST.get("product_id")
        if not str(product_id or "").isdigit():
            log.warning(
                "compare_toggle_invalid_payload",
                extra={"ui_surface": "compare_toggle", "product_id": product_id or ""},
            )
            return JsonResponse(
                {"ok": False, "error": "invalid product_id"}, status=400
            )
        try:
            product = Product.objects.only("id", "name", "slug", "price").get(
                pk=int(product_id)
            )
        except Product.DoesNotExist:
            log.warning(
                "compare_toggle_product_not_found",
                extra={"ui_surface": "compare_toggle", "product_id": int(product_id)},
            )
            return JsonResponse({"ok": False, "error": "product_not_found"}, status=404)
        product_id_int = int(product_id)
        compare_ids = _compare_ids(request)
        added = False
        if product_id_int in compare_ids:
            compare_ids = [pid for pid in compare_ids if pid != product_id_int]
        else:
            compare_ids = [product_id_int] + [
                pid for pid in compare_ids if pid != product_id_int
            ]
            compare_ids = compare_ids[:COMPARE_LIMIT]
            added = True
        compare_ids = _set_compare_ids(request, compare_ids)
        compare_products = _ordered_products_with_related(compare_ids, include_rating=False)
        log.info(
            "compare_toggle_ok",
            extra={
                "ui_surface": "compare_toggle",
                "product_id": product_id_int,
                "in_compare": added,
                "compare_count": len(compare_ids),
                "compare_limit": COMPARE_LIMIT,
            },
        )
        return JsonResponse(
            {
                "ok": True,
                "in_compare": added,
                "compare_count": len(compare_ids),
                "compare_ids": compare_ids,
                "compare_items": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "slug": item.slug,
                        "brand_name": getattr(item.brand, "name", ""),
                    }
                    for item in compare_products[:COMPARE_LIMIT]
                ],
                "tracking": {
                    "event": "compare_add" if added else "compare_remove",
                    "ecommerce": {"items": [_tracking_item_from_product(product)]},
                },
            }
        )


class ComparePageView(TemplateView):
    template_name = "shopfront/compare.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        products = _ordered_products_with_related(
            _compare_ids(self.request), include_rating=True
        )
        ctx["products"] = products
        ctx["compare_rows"] = _compare_fields(products)
        ctx.update(
            _seo_context(
                self.request,
                title="Сравнение товаров — Servio",
                description="Сравнение товаров по цене, бренду, серии, наличию, срокам поставки и ключевым характеристикам.",
                canonical=_absolute_url(self.request, reverse("compare_page")),
                robots="noindex,follow",
            )
        )
        return ctx


class FavoritesPageView(LoginRequiredMixin, TemplateView):
    template_name = "shopfront/favorites.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        product_ids = list(
            FavoriteProduct.objects.filter(user=self.request.user)
            .order_by("-created_at")
            .values_list("product_id", flat=True)[:300]
        )
        ctx["products"] = _ordered_products_with_related(
            product_ids, include_rating=True
        )
        ctx["category_subscriptions"] = (
            CategorySubscription.objects.select_related("category")
            .filter(user=self.request.user)
            .order_by("-created_at")[:12]
        )
        ctx["brand_subscriptions"] = (
            BrandSubscription.objects.select_related("brand")
            .filter(user=self.request.user)
            .order_by("-created_at")[:12]
        )
        ctx["saved_lists"] = _saved_list_queryset(self.request.user)[:8]
        ctx.update(
            _seo_context(
                self.request,
                title="Избранное — Servio",
                description="Список сохранённых товаров в аккаунте Servio.",
                robots="noindex,nofollow",
            )
        )
        return ctx


class SavedListsPageView(LoginRequiredMixin, TemplateView):
    template_name = "shopfront/saved_lists.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    @log_calls(log)
    def post(self, request, *args, **kwargs):
        action = (request.POST.get("action") or "").strip()
        service = SavedListOperationService(request.user)
        result = None

        if action == "create":
            name = request.POST.get("name", "")
            description = request.POST.get("description", "")
            result = service.create_list(name=name, description=description)
        elif action == "delete":
            list_id = request.POST.get("list_id")
            if str(list_id or "").isdigit():
                result = service.delete_list(int(list_id))
        elif action == "create_from_favorites":
            product_ids = list(
                FavoriteProduct.objects.filter(user=request.user)
                .order_by("-created_at")
                .values_list("product_id", flat=True)[:80]
            )
            if product_ids:
                result = service.create_list(
                    name="Из избранного", source=SavedList.Source.FAVORITES
                )
                if result.success and result.list_id:
                    service.add_products_to_list(result.list_id, product_ids)
        elif action == "create_from_cart":
            cart = _cart(request)
            product_ids = []
            quantities = {}
            for raw_id, payload in cart.items():
                if str(raw_id).isdigit():
                    product_id = int(raw_id)
                    product_ids.append(product_id)
                    quantities[product_id] = max(
                        1, int((payload or {}).get("qty") or 1)
                    )
            if product_ids:
                result = service.create_list(
                    name="Текущая корзина", source=SavedList.Source.CART
                )
                if result.success and result.list_id:
                    service.add_products_to_list(
                        result.list_id, product_ids, quantities=quantities
                    )
                    for product in Product.objects.filter(id__in=product_ids):
                        record_recommendation_event(
                            request=request,
                            event_name="saved_list_add",
                            product=product,
                            payload={
                                "surface": "saved_lists",
                                "saved_list_id": result.list_id,
                            },
                            logger=log,
                        )

        if result and result.success:
            messages.success(request, result.message)
        elif result and not result.success:
            messages.error(request, result.message)

        return redirect("saved_lists")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["saved_lists"] = _saved_list_queryset(self.request.user)[:100]
        ctx["favorites_count"] = FavoriteProduct.objects.filter(
            user=self.request.user
        ).count()
        ctx["cart_items_count"] = sum(
            max(0, int(item.get("qty", 0) or 0))
            for item in _cart(self.request).values()
        )
        ctx.update(
            _seo_context(
                self.request,
                title="Списки закупок — Servio",
                description="Сохранённые списки для repeat purchase, подготовки закупок и шаринга подборок внутри команды.",
                robots="noindex,nofollow",
            )
        )
        return ctx


class SavedListDetailView(LoginRequiredMixin, TemplateView):
    template_name = "shopfront/saved_list_detail.html"

    def _get_list(self):
        return get_object_or_404(
            SavedList.objects.prefetch_related(
                "items__product__images",
                "items__product__brand",
                "items__product__seller__seller_store",
            ),
            user=self.request.user,
            id=self.kwargs["list_id"],
        )

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    @log_calls(log)
    def post(self, request, *args, **kwargs):
        saved_list = self._get_list()
        action = (request.POST.get("action") or "").strip()
        service = SavedListOperationService(request.user)
        if action == "toggle_public":
            result = service.toggle_list_public(saved_list.id)
            if result.success:
                messages.success(request, result.message)
            else:
                messages.error(request, result.message)
        elif action == "move_to_cart":
            for item in saved_list.items.select_related("product").all():
                _cart_add_product(request, item.product_id, qty=item.quantity)
            messages.success(request, "Список добавлен в корзину")
        elif action == "remove_item":
            item_id = request.POST.get("item_id")
            if str(item_id or "").isdigit():
                result = service.remove_item_from_list(saved_list.id, int(item_id))
                if result.success:
                    messages.success(request, result.message)
                else:
                    messages.error(request, result.message)
        return redirect("saved_list_detail", list_id=saved_list.id)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        saved_list = self._get_list()
        product_ids = list(saved_list.items.values_list("product_id", flat=True))
        ctx["saved_list"] = saved_list
        ctx["products"] = _ordered_products_with_related(
            product_ids, include_rating=True
        )
        ctx["share_url"] = _absolute_url(
            self.request,
            reverse(
                "saved_list_shared", kwargs={"share_token": saved_list.share_token}
            ),
        )
        ctx.update(
            _seo_context(
                self.request,
                title=f"{saved_list.name} — список закупок Servio",
                description=_truncate_text(
                    saved_list.description or f"Список {saved_list.name} в Servio.", 160
                ),
                robots="noindex,nofollow",
            )
        )
        return ctx


class SharedSavedListView(TemplateView):
    template_name = "shopfront/saved_list_shared.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        saved_list = get_object_or_404(
            SavedList.objects.prefetch_related(
                "items__product__images", "items__product__brand"
            ),
            share_token=kwargs["share_token"],
            is_public=True,
        )
        ctx["saved_list"] = saved_list
        ctx["products"] = _ordered_products_with_related(
            list(saved_list.items.values_list("product_id", flat=True)),
            include_rating=True,
        )
        ctx.update(
            _seo_context(
                self.request,
                title=f"{saved_list.name} — публичный список Servio",
                description=_truncate_text(
                    saved_list.description
                    or f"Публичный список {saved_list.name} в Servio.",
                    160,
                ),
            )
        )
        return ctx


class SavedListFromOrderView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, order_id: int):
        order = get_object_or_404(
            Order.objects.prefetch_related("items"), id=order_id, placed_by=request.user
        )
        saved_list = SavedList.objects.create(
            user=request.user,
            name=f"Повтор заказа #{order.id}",
            description="Список, сформированный из ранее оформленного заказа",
            source=SavedList.Source.ORDER,
        )
        quantities = {item.product_id: item.qty for item in order.items.all()}
        _saved_list_add_products(
            saved_list, list(quantities.keys()), quantities=quantities
        )
        for item in order.items.select_related("product").all():
            record_recommendation_event(
                request=request,
                event_name="saved_list_add",
                product=item.product,
                payload={
                    "surface": "order_detail",
                    "saved_list_id": saved_list.id,
                    "order_id": order.id,
                },
                logger=log,
            )
        messages.success(request, "Заказ сохранён как список")
        return redirect("saved_list_detail", list_id=saved_list.id)


class SavedSearchesPageView(LoginRequiredMixin, TemplateView):
    template_name = "shopfront/saved_searches.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    @log_calls(log)
    def post(self, request, *args, **kwargs):
        action = (request.POST.get("action") or "").strip()
        service = SavedSearchService(request.user)
        result = None
        if action == "save":
            querystring = (request.POST.get("querystring") or "").strip()
            name = (request.POST.get("name") or "").strip() or "Мой фильтр"
            result = service.save_search(querystring=querystring, name=name)
        elif action == "delete":
            sid = request.POST.get("id")
            if str(sid or "").isdigit():
                result = service.delete_search(int(sid))
        if result and result.success:
            messages.success(request, result.message)
        elif result and not result.success:
            messages.error(request, result.message)
        return redirect("saved_searches")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["saved_searches"] = SavedSearch.objects.filter(
            user=self.request.user
        ).order_by("-created_at")[:200]
        ctx.update(
            _seo_context(
                self.request,
                title="Сохранённые поиски — Servio",
                description="Ваши сохранённые фильтры и поисковые запросы.",
                robots="noindex,nofollow",
            )
        )
        return ctx


class LiveSearchView(View):
    @log_calls(log)
    def get(self, request):
        query = request.GET.get("q")
        context = live_search_context(
            query=query,
            request=request,
            search_provider_getter=get_search_provider,
            logger=log,
        )
        log.info(
            "live_search_response_ready",
            extra={
                "ui_surface": "live_search",
                "query": (query or "").strip(),
                "provider": context.get("search_provider", "unknown"),
                "effective_query": context.get(
                    "search_effective_query", (query or "").strip()
                ),
                "rewritten_query": context.get("search_rewritten_query", ""),
                "rewrite_kind": context.get("search_rewrite_kind", ""),
                "show": context.get("show", False),
                "product_count": len(context.get("products", [])),
                "country_count": len(context.get("countries", [])),
                "suggestions_count": len(context.get("suggestions", [])),
            },
        )
        return render(
            request,
            "shopfront/partials/live_search_results.html",
            context,
        )
