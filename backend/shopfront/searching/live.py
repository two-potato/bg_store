"""Assembly helpers for the HTMX live-search widget.

The service hides provider selection and fallback logic from views and returns a
template-friendly context containing products, country suggestions, and query
suggestions.
"""

import time

from django.db.models import Prefetch, Q

from catalog.models import Product, ProductImage
from shopfront.models import SavedSearch
from shopfront.searching import backend as sf_search

from .observability import observe_search_response, observe_search_rewrite
from .service import DatabaseSearchProvider, suggest_query_corrections


def _recent_searches(request, q: str) -> list[dict]:
    items: list[dict] = []
    if request is None:
        return items

    recent = [value for value in request.session.get("recent_live_searches", []) if str(value).strip()]
    q_norm = q.strip()
    if q_norm:
        recent = [q_norm] + [value for value in recent if value != q_norm]
        request.session["recent_live_searches"] = recent[:6]
        request.session.modified = True
    for value in recent[:4]:
        items.append({"label": value, "href": f"/search/?q={value}"})
    if getattr(request.user, "is_authenticated", False):
        for search in SavedSearch.objects.filter(user=request.user).order_by("-created_at")[:4]:
            if any(item["label"] == search.name for item in items):
                continue
            items.append({"label": search.name, "href": f"/search/?{search.querystring}"})
    return items[:6]


def _facet_links(products) -> tuple[list[dict], list[dict], list[dict]]:
    brands: list[dict] = []
    categories: list[dict] = []
    sellers: list[dict] = []
    seen_brand_ids: set[int] = set()
    seen_category_ids: set[int] = set()
    seen_seller_slugs: set[str] = set()

    for product in products:
        brand = getattr(product, "brand", None)
        category = getattr(product, "category", None)
        store = getattr(getattr(product, "seller", None), "seller_store", None)
        if brand and brand.id not in seen_brand_ids and len(brands) < 4:
            seen_brand_ids.add(brand.id)
            brands.append({"label": brand.name, "href": f"/brands/{brand.slug}/"})
        if category and category.id not in seen_category_ids and len(categories) < 4:
            seen_category_ids.add(category.id)
            categories.append(
                {
                    "label": category.name,
                    "href": f"/categories/{getattr(category, 'full_slug_path', category.slug)}/",
                }
            )
        if store and store.slug not in seen_seller_slugs and len(sellers) < 4:
            seen_seller_slugs.add(store.slug)
            sellers.append({"label": store.name, "href": f"/vendors/{store.slug}/"})
    return brands, categories, sellers


def live_search_context(*, query: str, request=None, search_provider_getter, logger) -> dict:
    """Build the live-search response context for a raw user query."""
    q = (query or "").strip()
    if len(q) < 3:
        return {
            "q": q,
            "products": [],
            "countries": [],
            "suggestions": [],
            "brands": [],
            "categories": [],
            "sellers": [],
            "recent_searches": [],
            "quick_actions": [],
            "show": False,
        }

    opensearch_failed = False
    suggestions = []
    started = time.perf_counter()
    try:
        bundle = search_provider_getter().live_bundle(query=q, limit=8, country_limit=6)
        ids, countries, suggestions = bundle.product_ids, bundle.countries, bundle.suggestions
    except sf_search.OpenSearchUnavailable as exc:
        logger.warning("live_search_opensearch_unavailable", extra={"query": q, "reason": str(exc)})
        opensearch_failed = True
        ids, countries, suggestions = [], [], []

    logger.info(
        "live_search_result_ids",
        extra={"query": q, "count": len(ids), "country_count": len(countries), "suggestions_count": len(suggestions)},
    )
    base_qs = Product.objects.select_related("brand", "category", "seller", "seller__seller_store").prefetch_related(
        Prefetch(
            "images",
            queryset=ProductImage.objects.only("id", "product_id", "url", "alt", "ordering").order_by("ordering", "id"),
            to_attr="prefetched_images",
        )
    )

    if ids:
        order = {pid: idx for idx, pid in enumerate(ids)}
        products = sorted(base_qs.filter(id__in=ids), key=lambda product: order.get(product.id, 9999))
    elif not opensearch_failed:
        products = list(
            base_qs.filter(
                Q(name__icontains=q)
                | Q(sku__icontains=q)
                | Q(brand__name__icontains=q)
                | Q(category__name__icontains=q)
                | Q(seller__username__icontains=q)
                | Q(seller__seller_store__name__icontains=q)
                | Q(country_of_origin__name__icontains=q)
            )
            .distinct()
            .order_by("-is_new", "name")[:8]
        )
        logger.info("live_search_fallback_db", extra={"query": q, "count": len(products)})
        if not suggestions:
            seen = set()
            generated = []
            for product in products[:8]:
                for candidate in (product.name, f"{product.brand.name} {product.name}" if product.brand else "", product.sku):
                    txt = " ".join(str(candidate or "").split())
                    if not txt:
                        continue
                    key = txt.casefold()
                    if key in seen:
                        continue
                    seen.add(key)
                    generated.append(txt)
            suggestions = generated[:8]
        if not suggestions:
            suggestions = suggest_query_corrections(q, limit=6)
    else:
        fallback_bundle = DatabaseSearchProvider().live_bundle(query=q, limit=8, country_limit=0)
        bundle = fallback_bundle
        ids = fallback_bundle.product_ids
        suggestions = suggestions or fallback_bundle.suggestions
        products = list(base_qs.filter(id__in=ids).distinct().order_by("-is_new", "name")[:8])
        if not suggestions:
            suggestions = suggest_query_corrections(q, limit=6)

    observe_search_rewrite(
        surface="live_search",
        rewrite_kind=getattr(bundle, "rewrite_kind", ""),
        logger=logger,
        original_query=q,
        effective_query=getattr(bundle, "effective_query", q),
        rewritten_query=getattr(bundle, "rewritten_query", ""),
    )
    observe_search_response(
        surface="live_search",
        provider=getattr(bundle, "provider", "unknown"),
        query=q,
        effective_query=getattr(bundle, "effective_query", q),
        rewritten_query=getattr(bundle, "rewritten_query", ""),
        rewrite_kind=getattr(bundle, "rewrite_kind", ""),
        duration_seconds=time.perf_counter() - started,
        result_count=len(products),
        suggestions_count=len(suggestions[:8]),
        countries_count=len(countries),
        top_product_ids=[product.id for product in products[:8]],
        logger=logger,
    )

    brands, categories, sellers = _facet_links(products)
    recent_searches = _recent_searches(request, q)
    quick_actions = [
        {"label": "Все результаты", "href": f"/search/?q={q}", "meta": "Открыть каталог"},
        {"label": "Сравнение", "href": "/compare/", "meta": "Перейти к сравнению"},
    ]
    if request is not None and getattr(request.user, "is_authenticated", False):
        quick_actions.append({"label": "Списки закупок", "href": "/lists/", "meta": "Сохранить подборку"})
        quick_actions.append({"label": "Сохранённые поиски", "href": "/saved-searches/", "meta": "Вернуться к сценариям"})

    return {
        "q": q,
        "products": products,
        "countries": countries,
        "suggestions": suggestions[:8],
        "brands": brands,
        "categories": categories,
        "sellers": sellers,
        "recent_searches": recent_searches,
        "quick_actions": quick_actions,
        "show": True,
        "search_provider": getattr(bundle, "provider", "unknown"),
        "search_effective_query": getattr(bundle, "effective_query", q),
        "search_rewritten_query": getattr(bundle, "rewritten_query", ""),
        "search_rewrite_kind": getattr(bundle, "rewrite_kind", ""),
    }
