"""Catalog and filter suggestion UI views."""

from __future__ import annotations

import json
import time
from urllib.parse import urlencode

from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Case, IntegerField, When, Q
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views import View

from catalog.models import Category, Product, SellerOffer
from core.logging_utils import log_calls
from commerce.models import SellerStore

from ..catalog_selectors import (
    cached_catalog_default_page_ids as _cached_catalog_default_page_ids,
    cached_catalog_default_total_count as _cached_catalog_default_total_count,
    catalog_price_stats as _catalog_price_stats,
    category_breadcrumbs as _category_breadcrumbs,
    category_descendant_ids as _category_descendant_ids,
    category_option_rows as _category_option_rows,
    facet_option_counts as _facet_option_counts,
    ordered_products_with_related as _ordered_products_with_related,
    seller_facet_counts as _seller_facet_counts,
    with_rating as _with_rating,
)
from ..models import CategorySubscription
from ..recommendation_service import search_recovery_recommendations
from ..search_observability import observe_search_response, observe_search_rewrite
from ..search_service import DatabaseSearchProvider, suggest_query_corrections
import shopfront.views as shopfront_views
from . import (
    COMPARE_SESSION_KEY,
    _absolute_url,
    _cache_get,
    _cache_set,
    _cached_catalog_brands,
    _cached_catalog_categories,
    _cached_catalog_tags,
    _category_breadcrumb_label_map,
    _catalog_filter_suggestion_limit,
    _parse_decimal_filter,
    _selected_tag_object,
    _seo_context,
    _tracking_item_from_product,
    _visible_brand_filter_options,
    _visible_tag_filter_options,
    log,
)
from .. import search as sf_search


class CatalogView(View):
    @log_calls(log)
    def get(self, request):
        started = time.perf_counter()
        get_token(request)
        qs = Product.objects.all()
        brand = request.GET.get("brand")
        category = request.GET.get("category")
        seller = request.GET.get("seller")
        series = request.GET.get("series")
        q = request.GET.get("q", "")
        tag = request.GET.get("tag") or request.GET.get("tag_slug")
        availability = (request.GET.get("availability") or "").strip()
        delivery_eta = (request.GET.get("delivery_eta") or "").strip()
        min_price = _parse_decimal_filter(request.GET.get("min_price"))
        max_price = _parse_decimal_filter(request.GET.get("max_price"))
        sort = (request.GET.get("sort") or "").strip()
        try:
            page = int(request.GET.get("page") or 1)
        except (TypeError, ValueError):
            page = 1
        if page < 1:
            page = 1

        page_size = 16
        selected_category_obj = None
        selected_seller_store = None
        selected_series_obj = None

        if brand:
            if str(brand).isdigit():
                qs = qs.filter(brand_id=int(brand))
            else:
                qs = qs.none()
        if series:
            if str(series).isdigit():
                from catalog.models import Series

                selected_series_obj = (
                    Series.objects.select_related("brand")
                    .filter(id=int(series))
                    .only("id", "name", "brand_id", "brand__name", "brand__slug")
                    .first()
                )
            if selected_series_obj:
                qs = qs.filter(series_id=selected_series_obj.id)
            else:
                qs = qs.none()
        if category:
            if str(category).isdigit():
                selected_category_obj = Category.objects.select_related("parent").filter(id=int(category)).first()
            else:
                selected_category_obj = Category.objects.select_related("parent").filter(slug=category).first()
            if selected_category_obj:
                qs = qs.filter(category_id__in=_category_descendant_ids(selected_category_obj))
            else:
                qs = qs.none()

        search_ranked_ids = []
        search_suggestions: list[str] = []
        search_bundle = None
        if q:
            max_hits = int(getattr(settings, "OPENSEARCH_CATALOG_MAX_HITS", 2000))
            try:
                search_bundle = shopfront_views.get_search_provider().live_bundle(query=q, limit=max_hits, country_limit=0)
                search_ranked_ids = search_bundle.product_ids
                search_suggestions = search_bundle.suggestions[:8]
            except sf_search.OpenSearchUnavailable:
                search_bundle = DatabaseSearchProvider().live_bundle(query=q, limit=max_hits, country_limit=0)
                search_ranked_ids = search_bundle.product_ids
                search_suggestions = search_bundle.suggestions[:8]
            if not search_suggestions:
                search_suggestions = suggest_query_corrections(q, limit=6)
            if not search_ranked_ids:
                qs = qs.none()
            else:
                qs = qs.filter(id__in=search_ranked_ids)

        if tag:
            if tag.isdigit():
                qs = qs.filter(tags__id=int(tag))
            else:
                qs = qs.filter(tags__slug=tag)
        if seller:
            if str(seller).isdigit():
                qs = qs.filter(
                    Q(seller_id=int(seller)) | Q(seller_offers__seller_id=int(seller), seller_offers__status=SellerOffer.Status.ACTIVE)
                )
                selected_seller_store = SellerStore.objects.filter(owner_id=int(seller)).only("name", "slug", "owner_id").first()
            else:
                selected_seller_store = SellerStore.objects.filter(slug=seller).only("name", "slug", "owner_id").first()
                if selected_seller_store:
                    qs = qs.filter(
                        Q(seller_id=selected_seller_store.owner_id)
                        | Q(seller_offers__seller_id=selected_seller_store.owner_id, seller_offers__status=SellerOffer.Status.ACTIVE)
                    )
                else:
                    qs = qs.none()
        if availability == "in_stock":
            qs = qs.filter(
                Q(stock_qty__gt=0)
                | Q(seller_offers__status=SellerOffer.Status.ACTIVE, seller_offers__inventories__stock_qty__gt=0)
            )
        if delivery_eta == "fast":
            qs = qs.filter(Q(lead_time_days__lte=2) | Q(seller_offers__status=SellerOffer.Status.ACTIVE, seller_offers__lead_time_days__lte=2))
        elif delivery_eta == "week":
            qs = qs.filter(
                Q(lead_time_days__gt=2, lead_time_days__lte=7)
                | Q(seller_offers__status=SellerOffer.Status.ACTIVE, seller_offers__lead_time_days__gt=2, seller_offers__lead_time_days__lte=7)
            )
        elif delivery_eta == "planned":
            qs = qs.filter(Q(lead_time_days__gt=7) | Q(seller_offers__status=SellerOffer.Status.ACTIVE, seller_offers__lead_time_days__gt=7))
        if min_price is not None:
            qs = qs.filter(Q(price__gte=min_price) | Q(seller_offers__status=SellerOffer.Status.ACTIVE, seller_offers__price__gte=min_price))
        if max_price is not None:
            qs = qs.filter(Q(price__lte=max_price) | Q(seller_offers__status=SellerOffer.Status.ACTIVE, seller_offers__price__lte=max_price))
        qs = qs.distinct()
        facet_seed_qs = qs

        sort_map = {
            "new": ["-is_new", "name", "id"],
            "price_asc": ["price", "name", "id"],
            "price_desc": ["-price", "name", "id"],
            "name": ["name", "id"],
            "promo": ["-is_promo", "name", "id"],
            "rating_desc": ["-rating_avg", "-rating_count", "name", "id"],
        }
        include_rating = bool(getattr(settings, "ENABLE_CATALOG_RATING", settings.DEBUG))
        default_catalog = not any([brand, category, seller, series, q, tag, availability, delivery_eta, min_price, max_price]) and (not sort or sort == "new")
        cacheable_default_catalog = (
            default_catalog
            and page == 1
            and not request.user.is_authenticated
            and not request.headers.get("HX-Request")
            and not (request.session.get("cart") or {})
            and not (request.session.get(COMPARE_SESSION_KEY) or [])
        )
        if cacheable_default_catalog:
            cached_html = _cache_get("shopfront:catalog:html:v2:default")
            if cached_html:
                return HttpResponse(cached_html)

        if sort == "rating_desc":
            qs = _with_rating(qs).order_by(*sort_map["rating_desc"])
        elif q and search_ranked_ids and not sort:
            rank_order = Case(
                *[When(id=pid, then=pos) for pos, pid in enumerate(search_ranked_ids)],
                default=len(search_ranked_ids),
                output_field=IntegerField(),
            )
            qs = qs.order_by(rank_order)
        else:
            qs = qs.order_by(*sort_map.get(sort, ["-is_new", "name", "id"]))

        if default_catalog:
            total_count = _cached_catalog_default_total_count()
            num_pages = max(1, (total_count + page_size - 1) // page_size)
            safe_page = min(page, num_pages)
            page_ids = _cached_catalog_default_page_ids(page=safe_page, page_size=page_size)
            products_page = _ordered_products_with_related(page_ids, include_rating=include_rating)
            has_next = safe_page < num_pages
            next_page = safe_page + 1 if has_next else None
            current_page = safe_page
        else:
            paginator = Paginator(qs.values_list("id", flat=True), page_size)
            try:
                page_obj = paginator.page(page)
            except EmptyPage:
                page_obj = paginator.page(paginator.num_pages or 1)
            page_ids = list(page_obj.object_list)
            products_page = _ordered_products_with_related(page_ids, include_rating=include_rating)
            total_count = paginator.count
            has_next = page_obj.has_next()
            next_page = page_obj.next_page_number() if page_obj.has_next() else None
            current_page = page_obj.number

        base_params = {}
        if q:
            base_params["q"] = q
        if brand:
            base_params["brand"] = brand
        if category:
            base_params["category"] = category
        if seller:
            base_params["seller"] = seller
        if series:
            base_params["series"] = series
        if tag:
            base_params["tag"] = tag
        if delivery_eta:
            base_params["delivery_eta"] = delivery_eta
        if sort:
            base_params["sort"] = sort
        querystring_base = urlencode(base_params)
        category_reset_params = {k: v for k, v in base_params.items() if k != "category"}
        category_reset_querystring = urlencode(category_reset_params)
        category_reset_url = f"/catalog/?{category_reset_querystring}" if category_reset_querystring else "/catalog/"

        if request.headers.get("HX-Request") and request.GET.get("fragment") == "grid_append":
            return render(
                request,
                "shopfront/partials/catalog_grid_append.html",
                {
                    "products": products_page,
                    "has_next": has_next,
                    "next_page": next_page,
                    "querystring_base": querystring_base,
                },
            )

        brands = _cached_catalog_brands()
        categories = _cached_catalog_categories()
        category_depth_limit = max(0, int(getattr(settings, "CATALOG_FILTER_CATEGORY_DEPTH", 1)))
        if selected_category_obj:
            selected_depth = 0
            cursor = getattr(selected_category_obj, "parent", None)
            while cursor is not None and selected_depth < 8:
                selected_depth += 1
                cursor = getattr(cursor, "parent", None)
            category_depth_limit = max(category_depth_limit, selected_depth)
        category_rows = _category_option_rows(categories, max_depth=category_depth_limit)
        tags = _cached_catalog_tags()
        brand_id = int(brand) if brand and str(brand).isdigit() else None
        sel_brand = next((item for item in brands if brand_id is not None and item.id == brand_id), None)
        if category:
            if selected_category_obj:
                sel_category = selected_category_obj
            elif str(category).isdigit():
                sel_category = next((item for item in categories if item.id == int(category)), None)
            else:
                sel_category = next((item for item in categories if item.slug == category), None)
        else:
            sel_category = None
        sel_tag = _selected_tag_object(tag, tags)
        selected_category_children = [item for item in categories if sel_category and item.parent_id == sel_category.id][:8]
        facet_brand_options = _facet_option_counts(
            facet_seed_qs.exclude(brand_id=int(brand)) if brand and str(brand).isdigit() else facet_seed_qs,
            "brand",
            label_field="name",
            limit=10,
        )
        facet_seller_options = _seller_facet_counts(
            facet_seed_qs.exclude(seller_id=int(seller)) if seller and str(seller).isdigit() else facet_seed_qs,
            limit=10,
        )
        facet_price_stats = _catalog_price_stats(facet_seed_qs)
        fallback_product_ids = []
        if total_count == 0:
            fallback_product_ids = list(Product.objects.order_by("-is_promo", "-is_new", "name").values_list("id", flat=True)[:8])
        is_category_subscribed = bool(
            request.user.is_authenticated
            and sel_category is not None
            and CategorySubscription.objects.filter(user=request.user, category=sel_category).exists()
        )
        is_category_only = bool(category) and not any([q, brand, series, tag, sort, availability, delivery_eta, min_price, max_price]) and page == 1
        seo_robots = "index,follow" if (not any([q, brand, seller, series, tag, sort, availability, delivery_eta, min_price, max_price]) and page == 1) or is_category_only else "noindex,follow"
        if is_category_only:
            seo_canonical = _absolute_url(request, f"/catalog/?{urlencode({'category': category})}")
            category_name = sel_category.name if sel_category else str(category)
            seo_title = f"{category_name} — каталог Servio"
            seo_description = f"Товары категории «{category_name}» в каталоге Servio для HoReCa-закупок."
        else:
            seo_canonical = _absolute_url(request, "/catalog/")
            seo_title = "Каталог товаров для HoReCa — Servio"
            seo_description = "Каталог Servio: посуда, стекло, барный инвентарь, сервировка, упаковка, текстиль и расходные материалы для HoReCa."

        context = {
            "products": products_page,
            "brands": brands,
            "visible_brands": _visible_brand_filter_options(brands, facet_brand_options, sel_brand),
            "cats": categories,
            "category_rows": category_rows,
            "tags": tags,
            "visible_tags": _visible_tag_filter_options(tags, tag),
            "sort": sort or "new",
            "q": q,
            "brand": brand,
            "category": category,
            "tag": tag,
            "availability": availability,
            "delivery_eta": delivery_eta,
            "min_price": min_price,
            "max_price": max_price,
            "seller": seller,
            "series": series,
            "has_next": has_next,
            "next_page": next_page,
            "querystring_base": querystring_base,
            "total_count": total_count,
            "page": current_page,
            "page_size": page_size,
            "sel_brand": sel_brand,
            "sel_category": sel_category,
            "sel_tag": sel_tag,
            "sel_seller_store": selected_seller_store,
            "sel_series": selected_series_obj,
            "is_category_subscribed": is_category_subscribed,
            "selected_category_children": selected_category_children,
            "facet_brand_options": facet_brand_options,
            "facet_seller_options": facet_seller_options,
            "facet_price_min": facet_price_stats.get("min_price"),
            "facet_price_max": facet_price_stats.get("max_price"),
            "zero_results_products": _ordered_products_with_related(fallback_product_ids, include_rating=True),
            "category_breadcrumbs": _category_breadcrumbs(sel_category),
            "category_reset_url": category_reset_url,
            "catalog_tracking_payload": json.dumps(
                {
                    "event": "search" if q else "filter_use",
                    "search_term": q,
                    "filters": {
                        "brand": brand or "",
                        "category": getattr(sel_category, "slug", "") if sel_category else "",
                        "seller": getattr(selected_seller_store, "slug", "") if selected_seller_store else "",
                        "series": getattr(selected_series_obj, "name", "") if selected_series_obj else "",
                        "tag": tag or "",
                        "availability": availability or "",
                        "delivery_eta": delivery_eta or "",
                        "min_price": str(min_price or ""),
                        "max_price": str(max_price or ""),
                        "sort": sort or "new",
                    },
                    "ecommerce": {
                        "item_list_name": "catalog",
                        "items": [_tracking_item_from_product(item) for item in products_page[:12]],
                    },
                    "results_count": total_count,
                    "search_provider": getattr(search_bundle, "provider", ""),
                    "search_effective_query": getattr(search_bundle, "effective_query", q),
                    "search_rewritten_query": getattr(search_bundle, "rewritten_query", ""),
                    "search_rewrite_kind": getattr(search_bundle, "rewrite_kind", ""),
                    "search_recovery_shown": bool(total_count == 0 and (search_suggestions or q)),
                },
                ensure_ascii=False,
            ) if any([q, brand, category, tag, availability, delivery_eta, min_price, max_price, sort]) else "",
            "search_suggestions": [item for item in search_suggestions if item.casefold() != q.casefold()][:6],
            "search_corrections": [] if total_count else suggest_query_corrections(q, limit=4),
            **_seo_context(
                request,
                title=seo_title,
                description=seo_description,
                canonical=seo_canonical,
                robots=seo_robots,
            ),
        }
        if q and total_count <= 6:
            recovery_ctx = search_recovery_recommendations(q, user=request.user, request=request, limit=8)
            context["search_recovery_products"] = recovery_ctx["products"]
            context["search_recovery_tracking_payload"] = recovery_ctx["tracking_payload"]
            context["search_recovery_variant"] = recovery_ctx["variant"]
            context["search_recovery_title"] = "Похожие товары по запросу" if total_count == 0 else "Вам может подойти"
        if q and search_bundle is not None:
            observe_search_rewrite(
                surface="catalog",
                rewrite_kind=getattr(search_bundle, "rewrite_kind", ""),
                logger=log,
                original_query=q,
                effective_query=getattr(search_bundle, "effective_query", q),
                rewritten_query=getattr(search_bundle, "rewritten_query", ""),
            )
            observe_search_response(
                surface="catalog",
                provider=getattr(search_bundle, "provider", "unknown"),
                query=q,
                effective_query=getattr(search_bundle, "effective_query", q),
                rewritten_query=getattr(search_bundle, "rewritten_query", ""),
                rewrite_kind=getattr(search_bundle, "rewrite_kind", ""),
                duration_seconds=time.perf_counter() - started,
                result_count=total_count,
                suggestions_count=len(context["search_suggestions"]),
                top_product_ids=[item.id for item in products_page[:12]],
                logger=log,
            )
        if cacheable_default_catalog:
            html = render_to_string("shopfront/catalog.html", context, request=request)
            _cache_set("shopfront:catalog:html:v2:default", html, timeout=20)
            return HttpResponse(html)
        return render(request, "shopfront/catalog.html", context)


class CatalogFilterSuggestionsView(View):
    @log_calls(log)
    def get(self, request):
        kind = (request.GET.get("kind") or "").strip().lower()
        query = " ".join((request.GET.get("q") or "").strip().split())
        limit = _catalog_filter_suggestion_limit()
        if kind not in {"brand", "category", "tag"}:
            return JsonResponse({"items": [], "error": "invalid_kind"}, status=400)
        if len(query) < 2:
            return JsonResponse({"items": []})

        normalized_query = query.casefold()
        items = []
        seen = set()

        if kind == "brand":
            for brand in _cached_catalog_brands():
                name = (brand.name or "").strip()
                if not name or normalized_query not in name.casefold():
                    continue
                key = name.casefold()
                if key in seen:
                    continue
                seen.add(key)
                items.append({"value": str(brand.id), "label": name, "hint": f"ID {brand.id}"})
                if len(items) >= limit:
                    break
        elif kind == "tag":
            for tag_obj in _cached_catalog_tags():
                name = (tag_obj.name or "").strip()
                slug = (tag_obj.slug or "").strip()
                haystacks = [name.casefold(), slug.casefold()]
                if not any(normalized_query in haystack for haystack in haystacks if haystack):
                    continue
                key = slug or name.casefold()
                if key in seen:
                    continue
                seen.add(key)
                items.append({"value": slug or str(tag_obj.id), "label": name, "hint": slug})
                if len(items) >= limit:
                    break
        else:
            categories = _cached_catalog_categories()
            breadcrumb_map = _category_breadcrumb_label_map(categories)
            for category in categories:
                name = (category.name or "").strip()
                slug = (category.slug or "").strip()
                breadcrumb = breadcrumb_map.get(category.id, name)
                haystacks = [name.casefold(), slug.casefold(), breadcrumb.casefold()]
                if not any(normalized_query in haystack for haystack in haystacks if haystack):
                    continue
                key = slug or str(category.id)
                if key in seen:
                    continue
                seen.add(key)
                items.append({"value": slug or str(category.id), "label": name, "hint": breadcrumb})
                if len(items) >= limit:
                    break

        return JsonResponse({"items": items})
