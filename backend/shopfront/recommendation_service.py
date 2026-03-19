from __future__ import annotations

from collections import Counter
import logging

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q

from catalog.models import Product

from .catalog_selectors import ordered_products_with_related
from .recommendation_experiments import recommendation_variant_for_request
from .recommendation_events import recommendation_impression_payload
from .recommendation_observability import observe_recommendation_selection
from .recommendation_ranker import rerank_product_ids
from .recommendation_selectors import (
    hybrid_affinity_candidates,
    opensearch_similar_products,
    opensearch_substitute_products,
    personalized_candidate_ids,
    popularity_snapshot_ids,
    product_affinity_ids,
    recommendation_set_ids,
    seller_cross_sell_candidate_ids,
    user_replenishment_ids,
    user_reorder_ids,
    user_affinity_seed_ids,
    watchlist_candidate_ids,
)
from .recommendations import featured_collection_ids, brand_highlight_ids


log = logging.getLogger("shopfront")


def _cached_ids(key: str, ttl: int, builder):
    ids = cache.get(key)
    if ids is None:
        ids = builder()
        cache.set(key, ids, ttl)
    return list(ids or [])


def _materialized_or(kind: str, *, scope_type: str, scope_id: int = 0, limit: int, fallback):
    ids = recommendation_set_ids(kind, scope_type=scope_type, scope_id=scope_id, limit=limit)
    if ids:
        return ids
    return fallback()


def home_recommendations_context(user, *, request=None, limit: int = 8) -> dict:
    variant = recommendation_variant_for_request(request) if request is not None else "control"
    recommended_ids = _materialized_or(
        "personalized_home",
        scope_type="user",
        scope_id=getattr(user, "id", 0) or 0,
        limit=limit,
        fallback=lambda: rerank_product_ids(
            personalized_candidate_ids(user, limit=limit * 3) + hybrid_affinity_candidates(user, limit=limit * 2),
            user=user,
            source_name="home_for_you",
            experiment_variant=variant,
            limit=limit,
        ),
    )
    recent_ids = _materialized_or(
        "recently_viewed_home",
        scope_type="user",
        scope_id=getattr(user, "id", 0) or 0,
        limit=limit,
        fallback=lambda: user_affinity_seed_ids(user, limit=limit),
    )
    watchlist_ids = _materialized_or(
        "watchlist_home",
        scope_type="user",
        scope_id=getattr(user, "id", 0) or 0,
        limit=limit,
        fallback=lambda: rerank_product_ids(
            watchlist_candidate_ids(user, limit=limit * 2),
            user=user,
            source_name="home_watchlist",
            experiment_variant=variant,
            limit=limit,
        ),
    )
    global_popular_ids = popularity_snapshot_ids(limit=limit)
    reorder_ids = user_replenishment_ids(user, limit=limit)
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
            strategy="materialized_or_ranked",
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
        "recommended_for_you_tracking_payload": recommendation_impression_payload("home_for_you", recommended, surface="home", experiment_variant=variant),
        "home_recently_viewed_tracking_payload": recommendation_impression_payload("home_recently_viewed", recent, surface="home", experiment_variant=variant),
        "watchlist_products_tracking_payload": recommendation_impression_payload("home_watchlist", watchlist, surface="home", experiment_variant=variant),
        "home_popular_products_tracking_payload": recommendation_impression_payload("home_popular", popular, surface="home", experiment_variant=variant),
        "home_replenishment_tracking_payload": recommendation_impression_payload("home_replenishment", reorder, surface="home", experiment_variant=variant),
        "featured_collection_ids": featured_collection_ids(limit=3),
        "featured_brand_ids": brand_highlight_ids(limit=6),
    }


def product_detail_recommendations(product: Product, *, user=None, request=None, limit: int = 12) -> dict:
    cache_ttl = int(getattr(settings, "CACHE_TTL_PDP_RECOMMENDATIONS", 180))
    variant = recommendation_variant_for_request(request) if request is not None else "control"

    def _build_similar():
        candidate_ids = (
            opensearch_similar_products(product, limit=limit * 2)
            + product_affinity_ids(product, affinity_type="similar", limit=limit)
            + product_affinity_ids(product, affinity_type="substitute", limit=limit)
        )
        return rerank_product_ids(candidate_ids, user=user, source_product=product, source_name="product_similar", experiment_variant=variant, limit=limit)

    def _build_accessories():
        candidate_ids = seller_cross_sell_candidate_ids(product, limit=max(8, limit))
        return rerank_product_ids(candidate_ids, user=user, source_product=product, source_name="product_accessories", experiment_variant=variant, limit=8)

    def _build_substitutes():
        candidate_ids = opensearch_substitute_products(product, limit=limit * 2) + product_affinity_ids(product, affinity_type="substitute", limit=limit)
        return rerank_product_ids(candidate_ids, user=user, source_product=product, source_name="product_substitutes", experiment_variant=variant, limit=8)

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
    cache_ttl = int(getattr(settings, "CACHE_TTL_PDP_RECOMMENDATIONS", 180))
    variant = recommendation_variant_for_request(request) if request is not None else "control"
    if section == "fbt":
        ids = _cached_ids(
            f"shopfront:reco:fbt:v2:{product.id}",
            cache_ttl,
            lambda: _materialized_or(
                "fbt",
                scope_type="product",
                scope_id=product.id,
                limit=8,
                fallback=lambda: rerank_product_ids(
                    product_affinity_ids(product, affinity_type="co_purchase", limit=16),
                    user=user,
                    source_product=product,
                    source_name="product_frequently_bought_together",
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
            "tracking_payload": recommendation_impression_payload("product_frequently_bought_together", products, surface="pdp", experiment_variant=variant),
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
                fallback=lambda: rerank_product_ids(
                    seller_cross_sell_candidate_ids(product, limit=12),
                    user=user,
                    source_product=product,
                    source_name="product_seller_cross_sell",
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
            "tracking_payload": recommendation_impression_payload("product_seller_cross_sell", products, surface="pdp", experiment_variant=variant),
        }
    raise ValueError(f"Unknown recommendation section: {section}")


def cart_recommendations(products, *, user=None, request=None, limit: int = 8) -> dict:
    variant = recommendation_variant_for_request(request) if request is not None else "control"
    cart_ids = {product.id for product in products}
    seller_ids = {product.seller_id for product in products if product.seller_id}
    candidate_ids = list(
        Product.objects.filter(seller_id__in=seller_ids)
        .exclude(id__in=cart_ids)
        .order_by("-is_promo", "-is_new", "name")
        .values_list("id", flat=True)[: limit * 3]
    )
    ranked_ids = rerank_product_ids(candidate_ids, user=user, cart_product_ids=cart_ids, source_name="cart_cross_sell", experiment_variant=variant, limit=limit)
    ranked_products = ordered_products_with_related(ranked_ids, include_rating=True)
    observe_recommendation_selection(surface="cart", source="cart_cross_sell", variant=variant, strategy="seller_cross_sell", candidate_count=len(candidate_ids), product_ids=ranked_ids[:12], logger=log)
    return {
        "products": ranked_products,
        "tracking_payload": recommendation_impression_payload("cart_cross_sell", ranked_products, surface="cart", experiment_variant=variant),
    }


def checkout_recommendations(products, *, user=None, request=None, limit: int = 6) -> dict:
    variant = recommendation_variant_for_request(request) if request is not None else "control"
    cart_ids = {product.id for product in products}
    seller_ids = {product.seller_id for product in products if product.seller_id}
    candidate_ids = list(
        Product.objects.filter(seller_id__in=seller_ids, stock_qty__gt=0, min_order_qty__lte=5)
        .exclude(id__in=cart_ids)
        .order_by("lead_time_days", "-is_promo", "-is_new", "name")
        .values_list("id", flat=True)[: limit * 3]
    )
    ranked_ids = rerank_product_ids(candidate_ids, user=user, cart_product_ids=cart_ids, source_name="checkout_cross_sell", experiment_variant=variant, limit=limit)
    ranked_products = ordered_products_with_related(ranked_ids, include_rating=True)
    observe_recommendation_selection(surface="checkout", source="checkout_cross_sell", variant=variant, strategy="seller_cross_sell", candidate_count=len(candidate_ids), product_ids=ranked_ids[:12], logger=log)
    return {
        "products": ranked_products,
        "tracking_payload": recommendation_impression_payload("checkout_cross_sell", ranked_products, surface="checkout", experiment_variant=variant),
    }


def reorder_recommendations(user, *, limit: int = 8) -> list:
    ids = _materialized_or(
        "reorder",
        scope_type="user",
        scope_id=getattr(user, "id", 0) or 0,
        limit=limit,
        fallback=lambda: user_replenishment_ids(user, limit=limit) or user_reorder_ids(user, limit=limit),
    )
    return ordered_products_with_related(ids, include_rating=True)


def search_recovery_recommendations(query: str, *, user=None, request=None, limit: int = 8) -> dict:
    variant = recommendation_variant_for_request(request) if request is not None else "control"
    semantic_ids = []
    if query:
        from .recommendation_selectors import search_recovery_candidate_ids

        semantic_ids = search_recovery_candidate_ids(query, limit=limit * 2)
    affinity_ids = hybrid_affinity_candidates(user, limit=limit * 2) if user is not None else []
    popular_ids = popularity_snapshot_ids(limit=limit)
    ranked_ids = rerank_product_ids(
        semantic_ids + affinity_ids + popular_ids,
        user=user,
        source_name="search_recovery",
        experiment_variant=variant,
        limit=limit,
    )
    products = ordered_products_with_related(ranked_ids, include_rating=True)
    observe_recommendation_selection(surface="catalog", source="search_recovery", variant=variant, strategy="hybrid_recovery", candidate_count=len(semantic_ids) + len(affinity_ids) + len(popular_ids), product_ids=ranked_ids[:12], logger=log)
    return {
        "products": products,
        "tracking_payload": recommendation_impression_payload("search_recovery", products, surface="catalog", experiment_variant=variant),
        "variant": variant,
    }


def order_reorder_candidates(order, *, user=None, limit: int = 8) -> list:
    product_ids = list(order.items.values_list("product_id", flat=True))
    products = Product.objects.filter(
        Q(id__in=product_ids) | Q(category_id__in=Product.objects.filter(id__in=product_ids).values_list("category_id", flat=True))
    ).exclude(id__in=product_ids)
    ids = list(products.order_by("-is_promo", "-is_new", "name").values_list("id", flat=True)[:limit * 2])
    ranked_ids = rerank_product_ids(ids, user=user, source_name="order_repeat", experiment_variant="ranked_v2", limit=limit)
    return ordered_products_with_related(ranked_ids, include_rating=True)
