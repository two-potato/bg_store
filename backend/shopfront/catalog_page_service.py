"""Service layer for catalog page filtering, ranking, pagination, and SEO context."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Case, IntegerField, Q, When

from catalog.models import Product, SellerOffer
from commerce.models import SellerStore

from .catalog_selectors import (
    cached_catalog_default_page_ids as _cached_catalog_default_page_ids,
    cached_catalog_default_total_count as _cached_catalog_default_total_count,
    catalog_price_stats as _catalog_price_stats,
    category_breadcrumbs as _category_breadcrumbs,
    category_descendant_ids as _category_descendant_ids,
    category_option_rows as _category_option_rows,
    facet_option_counts as _facet_option_counts,
    ordered_products_with_related as _ordered_products_with_related,
    resolve_category_filter as _resolve_category_filter,
    seller_facet_counts as _seller_facet_counts,
    with_rating as _with_rating,
)
from .checkout_support import tracking_item_from_product as _tracking_item_from_product
from .models import CategorySubscription
from .recommendation.service import search_recovery_recommendations
from .searching import backend as sf_search
from .searching.observability import observe_search_response, observe_search_rewrite
from .searching.service import DatabaseSearchProvider, get_search_provider, suggest_query_corrections
from .views.constants import COMPARE_SESSION_KEY, log
from .views.utils_catalog import (
    CatalogRequestParams,
    _cache_get,
    _category_path,
    _category_url,
    _cached_catalog_brands,
    _cached_catalog_categories,
    _cached_catalog_tags,
    _selected_tag_object,
    _visible_brand_filter_options,
    _visible_tag_filter_options,
)
from .views.utils_seo import _absolute_url, _seo_context


DEFAULT_CATALOG_HTML_CACHE_KEY = "shopfront:catalog:html:v2:default"
DEFAULT_CATALOG_HTML_CACHE_TIMEOUT = 20


@dataclass(slots=True)
class CatalogRenderPlan:
    """Plan describing how the view should render the catalog response."""

    context: dict[str, Any]
    cacheable_default_catalog: bool
    cached_html: str | None = None
    append_fragment_context: dict[str, Any] | None = None


class CatalogPageService:
    """Build catalog page state outside the HTTP view layer."""

    def __init__(self, request, *, params: CatalogRequestParams, started_at: float) -> None:
        self.request = request
        self.params = params
        self.started_at = started_at
        self.qs = Product.objects.all()
        self.search_ranked_ids: list[int] = []
        self.search_suggestions: list[str] = []
        self.search_bundle = None
        self.selected_category_obj = None
        self.selected_seller_store = None
        self.selected_series_obj = None
        self.categories_cache = None

    def build(self) -> CatalogRenderPlan:
        """Build a full catalog render plan for the current request."""
        self._apply_primary_filters()
        self._apply_search_filter()
        self._apply_secondary_filters()
        self.qs = self.qs.distinct()
        facet_seed_qs = self.qs
        cacheable_default_catalog = self._is_cacheable_default_catalog()
        if cacheable_default_catalog:
            cached_html = _cache_get(DEFAULT_CATALOG_HTML_CACHE_KEY)
            if cached_html:
                return CatalogRenderPlan(
                    context={},
                    cacheable_default_catalog=True,
                    cached_html=cached_html,
                )

        qs = self._ordered_queryset(self.qs)
        products_page, total_count, has_next, next_page, current_page = self._paginate(qs)
        base_params = self.params.base_query_params()
        querystring_base = urlencode(base_params)
        category_reset_url = self._category_reset_url(base_params)

        if self._is_grid_append_request():
            return CatalogRenderPlan(
                context={},
                cacheable_default_catalog=cacheable_default_catalog,
                append_fragment_context={
                    "products": products_page,
                    "has_next": has_next,
                    "next_page": next_page,
                    "querystring_base": querystring_base,
                },
            )

        context = self._build_context(
            facet_seed_qs=facet_seed_qs,
            products_page=products_page,
            total_count=total_count,
            has_next=has_next,
            next_page=next_page,
            current_page=current_page,
            querystring_base=querystring_base,
            category_reset_url=category_reset_url,
        )
        self._observe_search(products_page=products_page, total_count=total_count, context=context)
        return CatalogRenderPlan(
            context=context,
            cacheable_default_catalog=cacheable_default_catalog,
        )

    def _apply_primary_filters(self) -> None:
        params = self.params
        if params.brand:
            if str(params.brand).isdigit():
                self.qs = self.qs.filter(brand_id=int(params.brand))
            else:
                self.qs = self.qs.none()

        if params.series:
            if str(params.series).isdigit():
                from catalog.models import Series

                self.selected_series_obj = (
                    Series.objects.select_related("brand")
                    .filter(id=int(params.series))
                    .only("id", "name", "brand_id", "brand__name", "brand__slug")
                    .first()
                )
            if self.selected_series_obj:
                self.qs = self.qs.filter(series_id=self.selected_series_obj.id)
            else:
                self.qs = self.qs.none()

        if params.category:
            self.categories_cache = _cached_catalog_categories()
            self.selected_category_obj = _resolve_category_filter(str(params.category), categories=self.categories_cache)
            if self.selected_category_obj:
                self.qs = self.qs.filter(category_id__in=_category_descendant_ids(self.selected_category_obj))
            else:
                self.qs = self.qs.none()

    def _apply_search_filter(self) -> None:
        if not self.params.q:
            return

        max_hits = int(getattr(settings, "OPENSEARCH_CATALOG_MAX_HITS", 2000))
        try:
            self.search_bundle = get_search_provider().live_bundle(query=self.params.q, limit=max_hits, country_limit=0)
        except sf_search.OpenSearchUnavailable:
            self.search_bundle = DatabaseSearchProvider().live_bundle(query=self.params.q, limit=max_hits, country_limit=0)

        self.search_ranked_ids = self.search_bundle.product_ids
        self.search_suggestions = self.search_bundle.suggestions[:8]
        if not self.search_suggestions:
            self.search_suggestions = suggest_query_corrections(self.params.q, limit=6)
        if not self.search_ranked_ids:
            self.qs = self.qs.none()
            return
        self.qs = self.qs.filter(id__in=self.search_ranked_ids)

    def _apply_secondary_filters(self) -> None:
        params = self.params
        if params.tag:
            if params.tag.isdigit():
                self.qs = self.qs.filter(tags__id=int(params.tag))
            else:
                self.qs = self.qs.filter(tags__slug=params.tag)

        if params.seller:
            self._apply_seller_filter()

        if params.availability == "in_stock":
            self.qs = self.qs.filter(
                Q(stock_qty__gt=0)
                | Q(
                    seller_offers__status=SellerOffer.Status.ACTIVE,
                    seller_offers__inventories__stock_qty__gt=0,
                )
            )
        if params.delivery_eta == "fast":
            self.qs = self.qs.filter(
                Q(lead_time_days__lte=2)
                | Q(
                    seller_offers__status=SellerOffer.Status.ACTIVE,
                    seller_offers__lead_time_days__lte=2,
                )
            )
        elif params.delivery_eta == "week":
            self.qs = self.qs.filter(
                Q(lead_time_days__gt=2, lead_time_days__lte=7)
                | Q(
                    seller_offers__status=SellerOffer.Status.ACTIVE,
                    seller_offers__lead_time_days__gt=2,
                    seller_offers__lead_time_days__lte=7,
                )
            )
        elif params.delivery_eta == "planned":
            self.qs = self.qs.filter(
                Q(lead_time_days__gt=7)
                | Q(
                    seller_offers__status=SellerOffer.Status.ACTIVE,
                    seller_offers__lead_time_days__gt=7,
                )
            )
        if params.min_price is not None:
            self.qs = self.qs.filter(
                Q(price__gte=params.min_price)
                | Q(
                    seller_offers__status=SellerOffer.Status.ACTIVE,
                    seller_offers__price__gte=params.min_price,
                )
            )
        if params.max_price is not None:
            self.qs = self.qs.filter(
                Q(price__lte=params.max_price)
                | Q(
                    seller_offers__status=SellerOffer.Status.ACTIVE,
                    seller_offers__price__lte=params.max_price,
                )
            )

    def _apply_seller_filter(self) -> None:
        seller = self.params.seller
        if str(seller).isdigit():
            seller_id = int(seller)
            self.qs = self.qs.filter(
                Q(seller_id=seller_id)
                | Q(
                    seller_offers__seller_id=seller_id,
                    seller_offers__status=SellerOffer.Status.ACTIVE,
                )
            )
            self.selected_seller_store = (
                SellerStore.objects.filter(owner_id=seller_id)
                .only("name", "slug", "owner_id")
                .first()
            )
            return

        self.selected_seller_store = (
            SellerStore.objects.filter(slug=seller).only("name", "slug", "owner_id").first()
        )
        if self.selected_seller_store:
            self.qs = self.qs.filter(
                Q(seller_id=self.selected_seller_store.owner_id)
                | Q(
                    seller_offers__seller_id=self.selected_seller_store.owner_id,
                    seller_offers__status=SellerOffer.Status.ACTIVE,
                )
            )
        else:
            self.qs = self.qs.none()

    def _ordered_queryset(self, queryset):
        sort_map = {
            "new": ["-is_new", "name", "id"],
            "price_asc": ["price", "name", "id"],
            "price_desc": ["-price", "name", "id"],
            "name": ["name", "id"],
            "promo": ["-is_promo", "name", "id"],
            "rating_desc": ["-rating_avg", "-rating_count", "name", "id"],
        }
        if self.params.sort == "rating_desc":
            return _with_rating(queryset).order_by(*sort_map["rating_desc"])
        if self.params.q and self.search_ranked_ids and not self.params.sort:
            rank_order = Case(
                *[When(id=pid, then=pos) for pos, pid in enumerate(self.search_ranked_ids)],
                default=len(self.search_ranked_ids),
                output_field=IntegerField(),
            )
            return queryset.order_by(rank_order)
        return queryset.order_by(*sort_map.get(self.params.sort, ["-is_new", "name", "id"]))

    def _paginate(self, queryset):
        page_size = 16
        if self._is_default_catalog():
            total_count = _cached_catalog_default_total_count()
            num_pages = max(1, (total_count + page_size - 1) // page_size)
            safe_page = min(self.params.page, num_pages)
            page_ids = _cached_catalog_default_page_ids(page=safe_page, page_size=page_size)
            products_page = _ordered_products_with_related(page_ids, include_rating=self._include_rating())
            has_next = safe_page < num_pages
            next_page = safe_page + 1 if has_next else None
            return products_page, total_count, has_next, next_page, safe_page

        paginator = Paginator(queryset.values_list("id", flat=True), page_size)
        try:
            page_obj = paginator.page(self.params.page)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages or 1)
        page_ids = list(page_obj.object_list)
        products_page = _ordered_products_with_related(page_ids, include_rating=self._include_rating())
        has_next = page_obj.has_next()
        next_page = page_obj.next_page_number() if has_next else None
        return products_page, paginator.count, has_next, next_page, page_obj.number

    def _build_context(
        self,
        *,
        facet_seed_qs,
        products_page,
        total_count: int,
        has_next: bool,
        next_page: int | None,
        current_page: int,
        querystring_base: str,
        category_reset_url: str,
    ) -> dict[str, Any]:
        page_size = 16
        brands = _cached_catalog_brands()
        categories = self.categories_cache or _cached_catalog_categories()
        category_lookup_by_id = {node.id: node for node in categories}
        category_rows = _category_option_rows(
            categories,
            max_depth=self._category_depth_limit(category_lookup_by_id),
        )
        tags = _cached_catalog_tags()
        brand_id = int(self.params.brand) if self.params.brand and str(self.params.brand).isdigit() else None
        sel_brand = next((item for item in brands if brand_id is not None and item.id == brand_id), None)
        sel_category = (
            self.selected_category_obj
            if self.params.category and self.selected_category_obj
            else _resolve_category_filter(str(self.params.category), categories=categories)
            if self.params.category
            else None
        )
        sel_tag = _selected_tag_object(self.params.tag, tags)
        selected_category_children = [
            item for item in categories if sel_category and item.parent_id == sel_category.id
        ][:8]
        facet_brand_options = _facet_option_counts(
            facet_seed_qs.exclude(brand_id=int(self.params.brand))
            if self.params.brand and str(self.params.brand).isdigit()
            else facet_seed_qs,
            "brand",
            label_field="name",
            limit=10,
        )
        facet_seller_options = _seller_facet_counts(
            facet_seed_qs.exclude(seller_id=int(self.params.seller))
            if self.params.seller and str(self.params.seller).isdigit()
            else facet_seed_qs,
            limit=10,
        )
        facet_price_stats = _catalog_price_stats(facet_seed_qs)
        fallback_product_ids = []
        if total_count == 0:
            fallback_product_ids = list(
                Product.objects.order_by("-is_promo", "-is_new", "name").values_list("id", flat=True)[:8]
            )
        is_category_subscribed = bool(
            self.request.user.is_authenticated
            and sel_category is not None
            and CategorySubscription.objects.filter(
                user=self.request.user,
                category=sel_category,
            ).exists()
        )
        seo_title, seo_description, seo_canonical, seo_robots = self._seo_fields(sel_category)
        context = {
            "products": products_page,
            "brands": brands,
            "visible_brands": _visible_brand_filter_options(brands, facet_brand_options, sel_brand),
            "cats": categories,
            "category_rows": category_rows,
            "tags": tags,
            "visible_tags": _visible_tag_filter_options(tags, self.params.tag),
            "sort": self.params.sort or "new",
            "q": self.params.q,
            "brand": self.params.brand,
            "category": self.params.category,
            "tag": self.params.tag,
            "availability": self.params.availability,
            "delivery_eta": self.params.delivery_eta,
            "min_price": self.params.min_price,
            "max_price": self.params.max_price,
            "seller": self.params.seller,
            "series": self.params.series,
            "has_next": has_next,
            "next_page": next_page,
            "querystring_base": querystring_base,
            "total_count": total_count,
            "page": current_page,
            "page_size": page_size,
            "sel_brand": sel_brand,
            "sel_category": sel_category,
            "sel_tag": sel_tag,
            "sel_seller_store": self.selected_seller_store,
            "sel_series": self.selected_series_obj,
            "is_category_subscribed": is_category_subscribed,
            "selected_category_children": selected_category_children,
            "facet_brand_options": facet_brand_options,
            "facet_seller_options": facet_seller_options,
            "facet_price_min": facet_price_stats.get("min_price"),
            "facet_price_max": facet_price_stats.get("max_price"),
            "zero_results_products": _ordered_products_with_related(
                fallback_product_ids,
                include_rating=True,
            ),
            "category_breadcrumbs": _category_breadcrumbs(sel_category, by_id=category_lookup_by_id),
            "category_reset_url": category_reset_url,
            "catalog_tracking_payload": self._catalog_tracking_payload(
                products_page=products_page,
                total_count=total_count,
                sel_category=sel_category,
            ),
            "search_suggestions": [
                item
                for item in self.search_suggestions
                if item.casefold() != self.params.q.casefold()
            ][:6],
            "search_corrections": [] if total_count else suggest_query_corrections(self.params.q, limit=4),
            **_seo_context(
                self.request,
                title=seo_title,
                description=seo_description,
                canonical=seo_canonical,
                robots=seo_robots,
            ),
        }
        if self.params.q and total_count == 0:
            recovery_ctx = search_recovery_recommendations(
                self.params.q,
                user=self.request.user,
                request=self.request,
                limit=8,
            )
            context["search_recovery_products"] = recovery_ctx["products"]
            context["search_recovery_tracking_payload"] = recovery_ctx["tracking_payload"]
            context["search_recovery_variant"] = recovery_ctx["variant"]
            context["search_recovery_title"] = (
                "Похожие товары по запросу" if total_count == 0 else "Вам может подойти"
            )
        return context

    def _observe_search(self, *, products_page, total_count: int, context: dict[str, Any]) -> None:
        if not (self.params.q and self.search_bundle is not None):
            return
        observe_search_rewrite(
            surface="catalog",
            rewrite_kind=getattr(self.search_bundle, "rewrite_kind", ""),
            logger=log,
            original_query=self.params.q,
            effective_query=getattr(self.search_bundle, "effective_query", self.params.q),
            rewritten_query=getattr(self.search_bundle, "rewritten_query", ""),
        )
        observe_search_response(
            surface="catalog",
            provider=getattr(self.search_bundle, "provider", "unknown"),
            query=self.params.q,
            effective_query=getattr(self.search_bundle, "effective_query", self.params.q),
            rewritten_query=getattr(self.search_bundle, "rewritten_query", ""),
            rewrite_kind=getattr(self.search_bundle, "rewrite_kind", ""),
            duration_seconds=time.perf_counter() - self.started_at,
            result_count=total_count,
            suggestions_count=len(context["search_suggestions"]),
            top_product_ids=[item.id for item in products_page[:12]],
            logger=log,
        )

    def _catalog_tracking_payload(self, *, products_page, total_count: int, sel_category) -> str:
        if not any(
            [
                self.params.q,
                self.params.brand,
                self.params.category,
                self.params.tag,
                self.params.availability,
                self.params.delivery_eta,
                self.params.min_price,
                self.params.max_price,
                self.params.sort,
            ]
        ):
            return ""
        return json.dumps(
            {
                "event": "search" if self.params.q else "filter_use",
                "search_term": self.params.q,
                "filters": {
                    "brand": self.params.brand or "",
                    "category": _category_path(sel_category) if sel_category else "",
                    "seller": getattr(self.selected_seller_store, "slug", "") if self.selected_seller_store else "",
                    "series": getattr(self.selected_series_obj, "name", "") if self.selected_series_obj else "",
                    "tag": self.params.tag or "",
                    "availability": self.params.availability or "",
                    "delivery_eta": self.params.delivery_eta or "",
                    "min_price": str(self.params.min_price or ""),
                    "max_price": str(self.params.max_price or ""),
                    "sort": self.params.sort or "new",
                },
                "ecommerce": {
                    "item_list_name": "catalog",
                    "items": [_tracking_item_from_product(item) for item in products_page[:12]],
                },
                "results_count": total_count,
                "search_provider": getattr(self.search_bundle, "provider", ""),
                "search_effective_query": getattr(self.search_bundle, "effective_query", self.params.q),
                "search_rewritten_query": getattr(self.search_bundle, "rewritten_query", ""),
                "search_rewrite_kind": getattr(self.search_bundle, "rewrite_kind", ""),
                "search_recovery_shown": bool(total_count == 0 and (self.search_suggestions or self.params.q)),
            },
            ensure_ascii=False,
        )

    def _seo_fields(self, sel_category):
        is_category_only = bool(self.params.category) and not any(
            [
                self.params.q,
                self.params.brand,
                self.params.series,
                self.params.tag,
                self.params.sort,
                self.params.availability,
                self.params.delivery_eta,
                self.params.min_price,
                self.params.max_price,
            ]
        ) and self.params.page == 1
        seo_robots = (
            "index,follow"
            if (
                not any(
                    [
                        self.params.q,
                        self.params.brand,
                        self.params.seller,
                        self.params.series,
                        self.params.tag,
                        self.params.sort,
                        self.params.availability,
                        self.params.delivery_eta,
                        self.params.min_price,
                        self.params.max_price,
                    ]
                )
                and self.params.page == 1
            )
            or is_category_only
            else "noindex,follow"
        )
        if is_category_only:
            category_name = sel_category.name if sel_category else str(self.params.category)
            return (
                f"{category_name} — каталог Servio",
                f"Товары категории «{category_name}» в каталоге Servio для HoReCa-закупок.",
                _absolute_url(self.request, _category_url(sel_category)),
                seo_robots,
            )
        if self.params.q:
            search_query = urlencode({"q": self.params.q}) if self.params.q else ""
            return (
                f"Поиск: {self.params.q} — Servio",
                f"Результаты поиска по запросу «{self.params.q}» в каталоге Servio.",
                _absolute_url(self.request, f"/search/{f'?{search_query}' if search_query else ''}"),
                seo_robots,
            )
        return (
            "Каталог товаров для HoReCa — Servio",
            "Каталог Servio: посуда, стекло, барный инвентарь, сервировка, упаковка, текстиль и расходные материалы для HoReCa.",
            _absolute_url(
                self.request,
                self.request.path if self.request.path.startswith("/catalog") else "/catalog/",
            ),
            seo_robots,
        )

    def _category_depth_limit(self, category_lookup_by_id: dict[int, Any]) -> int:
        depth_limit = max(0, int(getattr(settings, "CATALOG_FILTER_CATEGORY_DEPTH", 1)))
        if not self.selected_category_obj:
            return depth_limit
        selected_depth = 0
        cursor = self.selected_category_obj
        while cursor is not None and selected_depth < 8:
            parent_id = getattr(cursor, "parent_id", None)
            if not parent_id:
                break
            selected_depth += 1
            cursor = category_lookup_by_id.get(parent_id)
        return max(depth_limit, selected_depth)

    def _category_reset_url(self, base_params: dict[str, str]) -> str:
        category_reset_params = {key: value for key, value in base_params.items() if key != "category"}
        category_reset_querystring = urlencode(category_reset_params)
        if category_reset_querystring:
            return f"/catalog/?{category_reset_querystring}"
        return "/catalog/"

    def _include_rating(self) -> bool:
        return bool(getattr(settings, "ENABLE_CATALOG_RATING", settings.DEBUG))

    def _is_default_catalog(self) -> bool:
        return not any(
            [
                self.params.brand,
                self.params.category,
                self.params.seller,
                self.params.series,
                self.params.q,
                self.params.tag,
                self.params.availability,
                self.params.delivery_eta,
                self.params.min_price,
                self.params.max_price,
            ]
        ) and (not self.params.sort or self.params.sort == "new")

    def _is_cacheable_default_catalog(self) -> bool:
        return (
            self._is_default_catalog()
            and self.params.page == 1
            and not self.request.user.is_authenticated
            and not self.request.headers.get("HX-Request")
            and not (self.request.session.get("cart") or {})
            and not (self.request.session.get(COMPARE_SESSION_KEY) or [])
        )

    def _is_grid_append_request(self) -> bool:
        return bool(
            self.request.headers.get("HX-Request")
            and self.request.GET.get("fragment") == "grid_append"
        )
