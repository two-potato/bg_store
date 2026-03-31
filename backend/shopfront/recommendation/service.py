from __future__ import annotations

import logging

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q

from catalog.models import Product

from ..catalog_selectors import ordered_products_with_related
from .candidates import candidate_ids as candidate_ids_from_map, collect_candidate_map, trace_for_ids
from .experiments import recommendation_variant_for_request
from .events import recommendation_impression_payload
from .ml import active_model_for_surface
from .scoring_service import score_candidates_contract
from .observability import observe_recommendation_selection
from .policy import dismissed_product_ids
from .ranker import rerank_product_ids
from .selectors import (
    hybrid_affinity_candidates,
    opensearch_similar_products,
    opensearch_substitute_products,
    personalized_candidate_ids,
    popularity_snapshot_ids,
    product_affinity_ids,
    recommendation_set_ids,
    session_contextual_candidates,
    session_recently_viewed_ids,
    seller_cross_sell_candidate_ids,
    user_replenishment_ids,
    user_reorder_ids,
    user_affinity_seed_ids,
    watchlist_candidate_ids,
)
from .heuristics import featured_collection_ids, brand_highlight_ids


log = logging.getLogger("shopfront")
DEFAULT_RECOMMENDATION_MODEL_VERSION = "heuristic_ltr_prep_v1"


def _merge_ids(*groups: list[int], limit: int = 0) -> list[int]:
    """Internal helper for merge ids."""
    seen: set[int] = set()
    out: list[int] = []
    for group in groups:
        for value in group or []:
            try:
                product_id = int(value)
            except (TypeError, ValueError):
                continue
            if product_id <= 0 or product_id in seen:
                continue
            seen.add(product_id)
            out.append(product_id)
            if limit and len(out) >= limit:
                return out
    return out


def _cached_ids(key: str, ttl: int, builder):
    """Internal helper for cached ids."""
    ids = cache.get(key)
    if ids is None:
        ids = builder()
        if not isinstance(ids, list):
            ids = list(getattr(ids, "product_ids", []) or [])
        cache.set(key, ids, ttl)
    return list(ids or [])


def _materialized_or(kind: str, *, scope_type: str, scope_id: int = 0, limit: int, fallback):
    """Internal helper for materialized or."""
    ids = recommendation_set_ids(kind, scope_type=scope_type, scope_id=scope_id, limit=limit)
    if ids:
        return ids
    resolved = fallback()
    if not isinstance(resolved, list):
        return list(getattr(resolved, "product_ids", []) or [])
    return resolved


def _rank_candidate_map(
    candidate_map: dict[int, object],
    *,
    user=None,
    source_product: Product | None = None,
    cart_product_ids: set[int] | None = None,
    source_name: str = "",
    surface: str = "",
    request=None,
    experiment_variant: str = "control",
    limit: int = 8,
):
    """Internal helper for rank candidate map."""
    ordered_candidate_ids = candidate_ids_from_map(candidate_map)
    trace = trace_for_ids(candidate_map, ordered_candidate_ids)
    blocked_ids = dismissed_product_ids(request, surface=surface) if request is not None else set()
    result, contract = score_candidates_contract(
        surface=surface,
        candidate_ids=ordered_candidate_ids,
        user=user,
        request=request,
        source_product=source_product,
        cart_product_ids=cart_product_ids,
        source_name=source_name,
        experiment_variant=experiment_variant,
        candidate_reason_codes=trace.get("reason_codes_by_product"),
        candidate_sources=trace.get("candidate_sources_by_product"),
        blocked_product_ids=blocked_ids,
        limit=limit,
    )
    result.metadata.update({"strategy": contract.strategy, "model_version": contract.model_version, "variant": contract.variant})
    return result


def _tracking_payload(source: str, products, *, surface: str, experiment_variant: str, strategy: str, trace: dict | None = None) -> str:
    """Internal helper for tracking payload."""
    model_version = DEFAULT_RECOMMENDATION_MODEL_VERSION
    if experiment_variant == "ml_v1":
        model = active_model_for_surface(surface, variant="ml_v1")
        if model is not None:
            model_version = model.version
    return recommendation_impression_payload(
        source,
        products,
        surface=surface,
        experiment_variant=experiment_variant,
        strategy=strategy,
        model_version=model_version,
        trace=trace,
    )


def home_recommendations_context(user, *, request=None, limit: int = 8) -> dict:
    """Handle home recommendations context."""
    variant = recommendation_variant_for_request(request, surface="home") if request is not None else "control"
    user_id = getattr(user, "id", 0) or 0
    session_recent_ids = session_recently_viewed_ids(request, limit=max(limit * 2, 12)) if request is not None else []
    persisted_recent_ids = user_affinity_seed_ids(user, limit=max(limit * 2, 12))
    session_context_ids = session_contextual_candidates(request, limit=limit * 3) if request is not None else []
    affinity_probe_ids = hybrid_affinity_candidates(user, limit=4)
    watchlist_probe_ids = watchlist_candidate_ids(user, limit=4)
    reorder_probe_ids = user_replenishment_ids(user, limit=2)
    is_cold_start = not bool(user_id and (persisted_recent_ids or affinity_probe_ids or watchlist_probe_ids or reorder_probe_ids))
    recommended_ids = _materialized_or(
        "personalized_home",
        scope_type="user",
        scope_id=user_id,
        limit=limit,
        fallback=lambda: _rank_candidate_map(
            collect_candidate_map(
                [
                    ("personalized_seed", personalized_candidate_ids(user, limit=limit * 3), "user_affinity", "3.0"),
                    ("hybrid_affinity", hybrid_affinity_candidates(user, limit=limit * 2), "user_affinity", "2.0"),
                    ("session_context", session_context_ids, "session_context", "2.4"),
                    ("global_popular", popularity_snapshot_ids(limit=limit), "trending", "1.0"),
                    ("cold_start_popular", popularity_snapshot_ids(limit=limit * 2), "cold_start_popular", "0.8"),
                ],
                limit=limit * 6,
            ),
            user=user,
            source_name="home_for_you",
            surface="home",
            request=request,
            experiment_variant=variant,
            limit=limit,
        ),
    )
    if not isinstance(recommended_ids, list):
        recommended_ids = getattr(recommended_ids, "product_ids", []) or []
    recent_ids = _materialized_or(
        "recently_viewed_home",
        scope_type="user",
        scope_id=user_id,
        limit=limit,
        fallback=lambda: _merge_ids(session_recent_ids[:limit], persisted_recent_ids, limit=limit),
    )
    watchlist_ids = _materialized_or(
        "watchlist_home",
        scope_type="user",
        scope_id=user_id,
        limit=limit,
        fallback=lambda: _rank_candidate_map(
            collect_candidate_map(
                [
                    ("watchlist_brand_category", watchlist_candidate_ids(user, limit=limit * 2), "watchlist_match", "2.0"),
                    ("global_popular", popularity_snapshot_ids(limit=limit), "trending", "0.8"),
                ],
                limit=limit * 4,
            ),
            user=user,
            source_name="home_watchlist",
            surface="home",
            request=request,
            experiment_variant=variant,
            limit=limit,
        ),
    )
    if not isinstance(watchlist_ids, list):
        watchlist_ids = getattr(watchlist_ids, "product_ids", []) or []
    global_popular_ids = popularity_snapshot_ids(limit=limit)
    reorder_ids = user_replenishment_ids(user, limit=limit)
    recommended_candidate_map = collect_candidate_map(
        [
            ("personalized_seed", recommended_ids, "cold_start_popular" if is_cold_start else "user_affinity", "3.0"),
        ],
        limit=limit,
    )
    recent_candidate_map = collect_candidate_map(
        [
            ("recently_viewed", recent_ids, "recent_interest", "1.0"),
        ],
        limit=limit,
    )
    watchlist_candidate_map = collect_candidate_map(
        [
            ("watchlist_brand_category", watchlist_ids, "watchlist_match", "1.0"),
        ],
        limit=limit,
    )
    popular_candidate_map = collect_candidate_map(
        [
            ("global_popular", global_popular_ids, "trending", "1.0"),
        ],
        limit=limit,
    )
    reorder_candidate_map = collect_candidate_map(
        [
            ("replenishment_profile", reorder_ids, "replenishment_due", "1.0"),
        ],
        limit=limit,
    )
    recommended = ordered_products_with_related(recommended_ids, include_rating=True)
    recent = ordered_products_with_related(recent_ids, include_rating=True)
    watchlist = ordered_products_with_related(watchlist_ids, include_rating=True)
    popular = ordered_products_with_related(global_popular_ids, include_rating=True)
    reorder = ordered_products_with_related(reorder_ids, include_rating=True)
    for source, ids in (
        ("home_for_you", recommended_ids),
        ("home_recently_viewed", recent_ids),
        ("home_watchlist", watchlist_ids),
        ("home_popular", global_popular_ids),
        ("home_replenishment", reorder_ids),
    ):
        observe_recommendation_selection(
            surface="home",
            source=source,
            variant=variant,
            strategy="cold_start_ranked" if source == "home_for_you" and is_cold_start else "materialized_or_ranked",
            candidate_count=len(ids),
            product_ids=ids[:12],
            logger=log,
        )
    return {
        "recommended_for_you": recommended,
        "home_recently_viewed": recent,
        "watchlist_products": watchlist,
        "home_popular_products": popular,
        "home_replenishment_products": reorder,
        "recommendation_experiment_variant": variant,
        "recommended_for_you_tracking_payload": _tracking_payload("home_for_you", recommended, surface="home", experiment_variant=variant, strategy="cold_start_ranked" if is_cold_start else "materialized_or_ranked", trace=trace_for_ids(recommended_candidate_map, recommended_ids)),
        "home_recently_viewed_tracking_payload": _tracking_payload("home_recently_viewed", recent, surface="home", experiment_variant=variant, strategy="recent_history_session_aware", trace=trace_for_ids(recent_candidate_map, recent_ids)),
        "watchlist_products_tracking_payload": _tracking_payload("home_watchlist", watchlist, surface="home", experiment_variant=variant, strategy="materialized_or_ranked", trace=trace_for_ids(watchlist_candidate_map, watchlist_ids)),
        "home_popular_products_tracking_payload": _tracking_payload("home_popular", popular, surface="home", experiment_variant=variant, strategy="popularity_snapshot", trace=trace_for_ids(popular_candidate_map, global_popular_ids)),
        "home_replenishment_tracking_payload": _tracking_payload("home_replenishment", reorder, surface="home", experiment_variant=variant, strategy="replenishment_profile", trace=trace_for_ids(reorder_candidate_map, reorder_ids)),
        "featured_collection_ids": featured_collection_ids(limit=3),
        "featured_brand_ids": brand_highlight_ids(limit=6),
    }


def product_detail_recommendations(product: Product, *, user=None, request=None, limit: int = 12) -> dict:
    """Handle product detail recommendations."""
    cache_ttl = int(getattr(settings, "CACHE_TTL_PDP_RECOMMENDATIONS", 180))
    variant = recommendation_variant_for_request(request, surface="pdp") if request is not None else "control"

    def _build_similar():
        candidate_map = collect_candidate_map(
            [
                ("semantic_similar", opensearch_similar_products(product, limit=limit * 2), "semantic_similarity", "2.5"),
                ("co_view_affinity", product_affinity_ids(product, affinity_type="similar", limit=limit), "co_view", "2.0"),
                ("substitute_affinity", product_affinity_ids(product, affinity_type="substitute", limit=limit), "substitute_option", "1.5"),
            ],
            exclude={product.id},
            limit=limit * 4,
        )
        return _rank_candidate_map(candidate_map, user=user, source_product=product, source_name="product_similar", surface="pdp", request=request, experiment_variant=variant, limit=limit)

    def _build_accessories():
        candidate_map = collect_candidate_map(
            [
                ("seller_cross_sell", seller_cross_sell_candidate_ids(product, limit=max(8, limit)), "same_seller_cross_sell", "2.0"),
            ],
            exclude={product.id},
            limit=max(8, limit),
        )
        return _rank_candidate_map(candidate_map, user=user, source_product=product, source_name="product_accessories", surface="pdp", request=request, experiment_variant=variant, limit=8)

    def _build_substitutes():
        candidate_map = collect_candidate_map(
            [
                ("semantic_substitute", opensearch_substitute_products(product, limit=limit * 2), "substitute_option", "2.5"),
                ("substitute_affinity", product_affinity_ids(product, affinity_type="substitute", limit=limit), "substitute_option", "2.0"),
            ],
            exclude={product.id},
            limit=limit * 4,
        )
        return _rank_candidate_map(candidate_map, user=user, source_product=product, source_name="product_substitutes", surface="pdp", request=request, experiment_variant=variant, limit=8)

    similar_ids = _cached_ids(f"shopfront:reco:similar:v1:{product.id}", cache_ttl, _build_similar)
    accessory_ids = _cached_ids(f"shopfront:reco:accessories:v1:{product.id}", cache_ttl, _build_accessories)
    substitute_ids = _cached_ids(f"shopfront:reco:substitutes:v1:{product.id}", cache_ttl, _build_substitutes)

    for source, ids in (
        ("product_similar", similar_ids),
        ("product_accessories", accessory_ids),
        ("product_substitutes", substitute_ids),
    ):
        observe_recommendation_selection(
            surface="pdp",
            source=source,
            variant=variant,
            strategy="cached_ranked",
            candidate_count=len(ids),
            product_ids=ids[:12],
            logger=log,
        )
    return {
        "similar_products": ordered_products_with_related(similar_ids, include_rating=True),
        "accessory_products": ordered_products_with_related(accessory_ids, include_rating=True),
        "substitute_products": ordered_products_with_related(substitute_ids, include_rating=True),
        "recommendation_experiment_variant": variant,
    }


def product_section_context(product: Product, section: str, *, user=None, request=None) -> dict:
    """Handle product section context."""
    cache_ttl = int(getattr(settings, "CACHE_TTL_PDP_RECOMMENDATIONS", 180))
    variant = recommendation_variant_for_request(request, surface="pdp") if request is not None else "control"
    if section == "fbt":
        ids = _cached_ids(
            f"shopfront:reco:fbt:v2:{product.id}",
            cache_ttl,
            lambda: _materialized_or(
                "fbt",
                scope_type="product",
                scope_id=product.id,
                limit=8,
                fallback=lambda: _rank_candidate_map(
                    collect_candidate_map(
                        [
                            ("co_purchase_affinity", product_affinity_ids(product, affinity_type="co_purchase", limit=16), "co_purchase", "3.0"),
                        ],
                        exclude={product.id},
                        limit=16,
                    ),
                    user=user,
                    source_product=product,
                    source_name="product_frequently_bought_together",
                    surface="pdp",
                    request=request,
                    experiment_variant=variant,
                    limit=8,
                ),
            ),
        )
        products = ordered_products_with_related(ids, include_rating=True)
        observe_recommendation_selection(
            surface="pdp",
            source="product_frequently_bought_together",
            variant=variant,
            strategy="materialized_or_ranked",
            candidate_count=len(ids),
            product_ids=ids[:12],
            logger=log,
        )
        return {
            "products": products,
            "title": "Часто покупают вместе",
            "subtitle": "Основано на заказах и co-purchase паттернах внутри маркетплейса.",
            "recommendation_source": "product_frequently_bought_together",
            "tracking_payload": _tracking_payload("product_frequently_bought_together", products, surface="pdp", experiment_variant=variant, strategy="materialized_or_ranked", trace=trace_for_ids(collect_candidate_map([("co_purchase_affinity", ids, "co_purchase", "1.0")], limit=len(ids)), ids)),
        }
    if section == "seller-cross":
        ids = _cached_ids(
            f"shopfront:reco:sellercross:v2:{product.id}",
            cache_ttl,
            lambda: _materialized_or(
                "seller_cross_sell",
                scope_type="product",
                scope_id=product.id,
                limit=8,
                fallback=lambda: _rank_candidate_map(
                    collect_candidate_map(
                        [
                            ("seller_cross_sell", seller_cross_sell_candidate_ids(product, limit=12), "same_seller_cross_sell", "2.0"),
                        ],
                        exclude={product.id},
                        limit=12,
                    ),
                    user=user,
                    source_product=product,
                    source_name="product_seller_cross_sell",
                    surface="pdp",
                    request=request,
                    experiment_variant=variant,
                    limit=8,
                ),
            ),
        )
        products = ordered_products_with_related(ids, include_rating=True)
        observe_recommendation_selection(
            surface="pdp",
            source="product_seller_cross_sell",
            variant=variant,
            strategy="materialized_or_ranked",
            candidate_count=len(ids),
            product_ids=ids[:12],
            logger=log,
        )
        return {
            "products": products,
            "title": "Ещё у этого поставщика",
            "subtitle": "Смежные позиции того же продавца для upsell и cross-sell без лишнего трения.",
            "recommendation_source": "product_seller_cross_sell",
            "tracking_payload": _tracking_payload("product_seller_cross_sell", products, surface="pdp", experiment_variant=variant, strategy="materialized_or_ranked", trace=trace_for_ids(collect_candidate_map([("seller_cross_sell", ids, "same_seller_cross_sell", "1.0")], limit=len(ids)), ids)),
        }
    raise ValueError(f"Unknown recommendation section: {section}")


def cart_recommendations(products, *, user=None, request=None, limit: int = 8) -> dict:
    """Handle cart recommendations."""
    variant = recommendation_variant_for_request(request, surface="cart") if request is not None else "control"
    cart_ids = {product.id for product in products}
    seller_ids = {product.seller_id for product in products if product.seller_id}
    same_seller_ids = list(
        Product.objects.filter(seller_id__in=seller_ids)
        .exclude(id__in=cart_ids)
        .order_by("-is_promo", "-is_new", "name")
        .values_list("id", flat=True)[: limit * 3]
    )
    popular_same_category_ids = popularity_snapshot_ids(limit=limit)
    candidate_map = collect_candidate_map(
        [
            ("same_seller", same_seller_ids, "same_seller_cross_sell", "2.0"),
            ("cart_popular", popular_same_category_ids, "trending", "1.0"),
        ],
        exclude=cart_ids,
        limit=limit * 4,
    )
    ranked = _rank_candidate_map(candidate_map, user=user, cart_product_ids=cart_ids, source_name="cart_cross_sell", surface="cart", request=request, experiment_variant=variant, limit=limit)
    ranked_ids = ranked.product_ids
    ranked_products = ordered_products_with_related(ranked_ids, include_rating=True)
    observe_recommendation_selection(surface="cart", source="cart_cross_sell", variant=variant, strategy="multi_source_ranked", candidate_count=len(candidate_ids_from_map(candidate_map)), product_ids=ranked_ids[:12], logger=log)
    return {
        "products": ranked_products,
        "tracking_payload": _tracking_payload("cart_cross_sell", ranked_products, surface="cart", experiment_variant=variant, strategy="multi_source_ranked", trace=trace_for_ids(candidate_map, ranked_ids)),
    }


def checkout_recommendations(products, *, user=None, request=None, limit: int = 6) -> dict:
    """Handle checkout recommendations."""
    variant = recommendation_variant_for_request(request, surface="checkout") if request is not None else "control"
    cart_ids = {product.id for product in products}
    seller_ids = {product.seller_id for product in products if product.seller_id}
    same_seller_ids = list(
        Product.objects.filter(seller_id__in=seller_ids, stock_qty__gt=0, min_order_qty__lte=5)
        .exclude(id__in=cart_ids)
        .order_by("lead_time_days", "-is_promo", "-is_new", "name")
        .values_list("id", flat=True)[: limit * 3]
    )
    replenishment_ids = user_replenishment_ids(user, limit=limit) if user is not None else []
    candidate_map = collect_candidate_map(
        [
            ("same_seller_fast_stock", same_seller_ids, "same_seller_cross_sell", "2.0"),
            ("replenishment_profile", replenishment_ids, "replenishment_due", "1.5"),
        ],
        exclude=cart_ids,
        limit=limit * 4,
    )
    ranked = _rank_candidate_map(candidate_map, user=user, cart_product_ids=cart_ids, source_name="checkout_cross_sell", surface="checkout", request=request, experiment_variant=variant, limit=limit)
    ranked_ids = ranked.product_ids
    ranked_products = ordered_products_with_related(ranked_ids, include_rating=True)
    observe_recommendation_selection(surface="checkout", source="checkout_cross_sell", variant=variant, strategy="multi_source_ranked", candidate_count=len(candidate_ids_from_map(candidate_map)), product_ids=ranked_ids[:12], logger=log)
    return {
        "products": ranked_products,
        "tracking_payload": _tracking_payload("checkout_cross_sell", ranked_products, surface="checkout", experiment_variant=variant, strategy="multi_source_ranked", trace=trace_for_ids(candidate_map, ranked_ids)),
    }


def reorder_recommendations(user, *, limit: int = 8) -> list:
    """Handle reorder recommendations."""
    ids = _materialized_or(
        "reorder",
        scope_type="user",
        scope_id=getattr(user, "id", 0) or 0,
        limit=limit,
        fallback=lambda: user_replenishment_ids(user, limit=limit) or user_reorder_ids(user, limit=limit),
    )
    return ordered_products_with_related(ids, include_rating=True)


def search_recovery_recommendations(query: str, *, user=None, request=None, limit: int = 8) -> dict:
    """Handle search recovery recommendations."""
    variant = recommendation_variant_for_request(request, surface="catalog") if request is not None else "control"
    semantic_ids = []
    if query:
        from .selectors import search_recovery_candidate_ids

        semantic_ids = search_recovery_candidate_ids(query, limit=limit * 2)
    affinity_ids = hybrid_affinity_candidates(user, limit=limit * 2) if user is not None else []
    popular_ids = popularity_snapshot_ids(limit=limit)
    candidate_map = collect_candidate_map(
        [
            ("semantic_search_recovery", semantic_ids, "search_intent_match", "3.0"),
            ("hybrid_affinity", affinity_ids, "user_affinity", "1.5"),
            ("global_popular", popular_ids, "trending", "1.0"),
        ],
        limit=limit * 5,
    )
    ranked = _rank_candidate_map(candidate_map, user=user, source_name="search_recovery", surface="catalog", request=request, experiment_variant=variant, limit=limit)
    ranked_ids = ranked.product_ids
    products = ordered_products_with_related(ranked_ids, include_rating=True)
    observe_recommendation_selection(surface="catalog", source="search_recovery", variant=variant, strategy="hybrid_recovery", candidate_count=len(candidate_ids_from_map(candidate_map)), product_ids=ranked_ids[:12], logger=log)
    return {
        "products": products,
        "tracking_payload": _tracking_payload("search_recovery", products, surface="catalog", experiment_variant=variant, strategy="hybrid_recovery", trace=trace_for_ids(candidate_map, ranked_ids)),
        "variant": variant,
    }


def order_reorder_candidates(order, *, user=None, limit: int = 8) -> list:
    """Handle order reorder candidates."""
    product_ids = list(order.items.values_list("product_id", flat=True))
    products = Product.objects.filter(
        Q(id__in=product_ids) | Q(category_id__in=Product.objects.filter(id__in=product_ids).values_list("category_id", flat=True))
    ).exclude(id__in=product_ids)
    ids = list(products.order_by("-is_promo", "-is_new", "name").values_list("id", flat=True)[:limit * 2])
    ranked_ids = rerank_product_ids(ids, user=user, source_name="order_repeat", experiment_variant="ranked_v2", limit=limit)
    return ordered_products_with_related(ranked_ids, include_rating=True)
