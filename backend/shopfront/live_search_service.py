from django.db.models import Prefetch, Q

from catalog.models import Product, ProductImage
from shopfront import search as sf_search

from .search_service import DatabaseSearchProvider, suggest_query_corrections


def live_search_context(*, query: str, search_provider_getter, logger) -> dict:
    q = (query or "").strip()
    if len(q) < 3:
        return {"q": q, "products": [], "countries": [], "suggestions": [], "show": False}

    es_failed = False
    suggestions = []
    try:
        bundle = search_provider_getter().live_bundle(query=q, limit=8, country_limit=6)
        ids, countries, suggestions = bundle.product_ids, bundle.countries, bundle.suggestions
    except sf_search.ESSearchUnavailable as exc:
        logger.warning("live_search_es_unavailable", extra={"query": q, "reason": str(exc)})
        es_failed = True
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
    elif not es_failed:
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
        ids = fallback_bundle.product_ids
        suggestions = suggestions or fallback_bundle.suggestions
        products = list(base_qs.filter(id__in=ids).distinct().order_by("-is_new", "name")[:8])
        if not suggestions:
            suggestions = suggest_query_corrections(q, limit=6)

    return {"q": q, "products": products, "countries": countries, "suggestions": suggestions[:8], "show": True}
