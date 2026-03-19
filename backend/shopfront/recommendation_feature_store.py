from __future__ import annotations

from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Q
from django.utils import timezone

from catalog.models import Product, ProductReview
from commerce.models import StoreReview
from orders.models import OrderItem

from .models import (
    BrandSubscription,
    CategorySubscription,
    FavoriteProduct,
    PersistentCart,
    RecommendationEvent,
    RecommendationFeatureSnapshot,
    RecommendationPopularitySnapshot,
    RecommendationProductAffinity,
    RecommendationReplenishmentProfile,
    RecommendationUserAffinity,
    RecentlyViewedProduct,
    SavedSearch,
)


FEATURE_NAMES_V1 = [
    "user_is_authenticated",
    "user_recent_views_count",
    "user_favorites_count",
    "user_orders_count",
    "user_replenishment_count",
    "user_brand_subscriptions_count",
    "user_category_subscriptions_count",
    "user_saved_searches_count",
    "user_cart_items_count",
    "user_affinity_brand_score",
    "user_affinity_category_score",
    "user_affinity_seller_score",
    "user_affinity_tag_score",
    "user_price_band_entry",
    "user_price_band_mid",
    "user_price_band_premium",
    "product_is_new",
    "product_is_promo",
    "product_in_stock",
    "product_fast_delivery",
    "product_low_moq",
    "product_price_value",
    "product_rating_avg",
    "product_rating_count",
    "product_review_photo_count",
    "product_review_verified_ratio",
    "product_global_popularity_7d",
    "product_global_popularity_30d",
    "product_category_popularity_7d",
    "product_brand_popularity_7d",
    "product_seller_popularity_7d",
    "product_similar_edge_score",
    "product_copurchase_edge_score",
    "product_conversion_score",
    "product_purchase_count_30d",
    "product_view_count_7d",
    "product_add_to_cart_count_7d",
    "product_seller_rating_avg",
    "product_seller_review_count",
    "context_position",
    "context_position_inverse",
    "context_has_query",
    "context_query_length",
    "context_cart_size",
    "context_source_same_brand",
    "context_source_same_category",
    "context_source_same_seller",
    "context_candidate_source_count",
    "context_reason_count",
    "context_is_anonymous",
    "context_surface_home",
    "context_surface_catalog",
    "context_surface_pdp",
    "context_surface_cart",
    "context_surface_checkout",
]


def _snapshot(feature_set: str, scope_type: str, scope_id: int, *, payload: dict, surface: str = "", expires_in_seconds: int = 6 * 3600, metadata: dict | None = None):
    now = timezone.now()
    return RecommendationFeatureSnapshot.objects.create(
        feature_set=feature_set,
        scope_type=scope_type,
        scope_id=max(0, int(scope_id or 0)),
        surface=surface or "",
        payload=payload,
        generated_at=now,
        expires_at=now + timedelta(seconds=max(300, int(expires_in_seconds or 300))),
        metadata=metadata or {},
    )


def latest_feature_snapshot(*, feature_set: str, scope_type: str, scope_id: int, surface: str = "") -> RecommendationFeatureSnapshot | None:
    now = timezone.now()
    return (
        RecommendationFeatureSnapshot.objects.filter(
            feature_set=feature_set,
            scope_type=scope_type,
            scope_id=max(0, int(scope_id or 0)),
            surface=surface or "",
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .order_by("-generated_at", "-id")
        .first()
    )


def _popularity_score(*, product_id: int, scope_type: str, scope_id: int = 0, window: str = "7d") -> float:
    row = (
        RecommendationPopularitySnapshot.objects.filter(
            scope_type=scope_type,
            scope_id=max(0, int(scope_id or 0)),
            window=window,
            product_id=product_id,
        )
        .only("score")
        .first()
    )
    return float(getattr(row, "score", 0) or 0)


def build_user_feature_payload(user) -> dict:
    user_id = getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None
    if not user_id:
        return {
            "user_recent_views_count": 0,
            "user_favorites_count": 0,
            "user_orders_count": 0,
            "user_replenishment_count": 0,
            "user_brand_subscriptions_count": 0,
            "user_category_subscriptions_count": 0,
            "user_saved_searches_count": 0,
            "user_cart_items_count": 0,
            "affinity_scores": {},
            "price_band": "",
        }
    affinity_rows = list(
        RecommendationUserAffinity.objects.filter(user_id=user_id).only("dimension", "entity_id", "entity_key", "score")
    )
    affinity_scores: dict[str, dict[str, float]] = {"brand": {}, "category": {}, "seller": {}, "tag": {}, "price_band": {}}
    for row in affinity_rows:
        dimension = str(row.dimension or "")
        if dimension == "price_band":
            affinity_scores["price_band"][str(row.entity_key or "")] = float(row.score or 0)
        else:
            affinity_scores.setdefault(dimension, {})[str(int(row.entity_id or 0))] = float(row.score or 0)
    price_band = ""
    if affinity_scores["price_band"]:
        price_band = max(affinity_scores["price_band"].items(), key=lambda item: item[1])[0]
    cart_payload = dict(
        PersistentCart.objects.filter(user_id=user_id).values_list("payload", flat=True).first() or {}
    )
    return {
        "user_recent_views_count": int(RecentlyViewedProduct.objects.filter(user_id=user_id).count()),
        "user_favorites_count": int(FavoriteProduct.objects.filter(user_id=user_id).count()),
        "user_orders_count": int(OrderItem.objects.filter(order__placed_by_id=user_id).values("order_id").distinct().count()),
        "user_replenishment_count": int(RecommendationReplenishmentProfile.objects.filter(user_id=user_id).count()),
        "user_brand_subscriptions_count": int(BrandSubscription.objects.filter(user_id=user_id).count()),
        "user_category_subscriptions_count": int(CategorySubscription.objects.filter(user_id=user_id).count()),
        "user_saved_searches_count": int(SavedSearch.objects.filter(user_id=user_id).count()),
        "user_cart_items_count": int(
            sum(max(0, int((item or {}).get("qty", 0) or 0)) for item in cart_payload.values())
        ),
        "affinity_scores": affinity_scores,
        "price_band": price_band,
    }


def build_product_feature_payload(product: Product) -> dict:
    similar_score = (
        RecommendationProductAffinity.objects.filter(
            source_product_id=product.id,
            affinity_type=RecommendationProductAffinity.AffinityType.SIMILAR,
        )
        .aggregate(total=Count("id"))
        .get("total")
        or 0
    )
    copurchase_score = (
        RecommendationProductAffinity.objects.filter(
            source_product_id=product.id,
            affinity_type=RecommendationProductAffinity.AffinityType.CO_PURCHASE,
        )
        .aggregate(total=Count("id"))
        .get("total")
        or 0
    )
    reviews = ProductReview.objects.filter(product_id=product.id)
    review_summary = reviews.aggregate(avg_rating=Avg("rating"), count=Count("id"))
    seller_reviews = StoreReview.objects.filter(store__owner_id=product.seller_id) if product.seller_id else StoreReview.objects.none()
    seller_review_summary = seller_reviews.aggregate(avg_rating=Avg("rating"), count=Count("id"))
    purchase_count_30d = int(
        OrderItem.objects.filter(
            product_id=product.id,
            created_at__gte=timezone.now() - timedelta(days=30),
        ).count()
    )
    view_count_7d = int(
        RecentlyViewedProduct.objects.filter(
            product_id=product.id,
            updated_at__gte=timezone.now() - timedelta(days=7),
        ).count()
    )
    add_to_cart_count_7d = int(
        RecommendationEvent.objects.filter(
            event="add_to_cart",
            product_id=product.id,
            created_at__gte=timezone.now() - timedelta(days=7),
        ).count()
    )
    rating_count = int(review_summary.get("count") or 0)
    rating_avg = float(review_summary.get("avg_rating") or 0)
    return {
        "brand_id": int(product.brand_id or 0),
        "category_id": int(product.category_id or 0),
        "seller_id": int(product.seller_id or 0),
        "price_value": float(getattr(product, "display_price", getattr(product, "price", 0)) or 0),
        "is_new": bool(product.is_new),
        "is_promo": bool(product.is_promo),
        "in_stock": bool(product.display_stock_qty > 0),
        "fast_delivery": bool(product.display_lead_time_days <= 3),
        "low_moq": bool(product.display_min_order_qty <= 5),
        "rating_avg": rating_avg,
        "rating_count": rating_count,
        "review_photo_count": int(reviews.filter(photos__isnull=False).distinct().count()),
        "review_verified_ratio": float(
            reviews.filter(is_verified_purchase=True).count() / max(1, rating_count)
        ),
        "global_popularity_7d": _popularity_score(product_id=product.id, scope_type=RecommendationPopularitySnapshot.ScopeType.GLOBAL),
        "global_popularity_30d": _popularity_score(
            product_id=product.id,
            scope_type=RecommendationPopularitySnapshot.ScopeType.GLOBAL,
            window="30d",
        ),
        "category_popularity_7d": _popularity_score(product_id=product.id, scope_type=RecommendationPopularitySnapshot.ScopeType.CATEGORY, scope_id=int(product.category_id or 0)),
        "brand_popularity_7d": _popularity_score(product_id=product.id, scope_type=RecommendationPopularitySnapshot.ScopeType.BRAND, scope_id=int(product.brand_id or 0)),
        "seller_popularity_7d": _popularity_score(product_id=product.id, scope_type=RecommendationPopularitySnapshot.ScopeType.SELLER, scope_id=int(product.seller_id or 0)),
        "similar_edge_score": float(similar_score),
        "copurchase_edge_score": float(copurchase_score),
        "conversion_score": float((purchase_count_30d * 4) + (add_to_cart_count_7d * 2) + view_count_7d),
        "purchase_count_30d": purchase_count_30d,
        "view_count_7d": view_count_7d,
        "add_to_cart_count_7d": add_to_cart_count_7d,
        "seller_rating_avg": float(seller_review_summary.get("avg_rating") or 0),
        "seller_review_count": int(seller_review_summary.get("count") or 0),
    }


def build_global_feature_payload() -> dict:
    return {
        "total_products": int(Product.objects.filter(publication_status=Product.PublicationStatus.PUBLISHED).count()),
        "global_popular_count": int(
            RecommendationPopularitySnapshot.objects.filter(
                scope_type=RecommendationPopularitySnapshot.ScopeType.GLOBAL,
                scope_id=0,
                window="7d",
            ).count()
        ),
    }


def refresh_recommendation_feature_snapshots(*, user_limit: int = 1000, product_limit: int = 2000) -> dict:
    RecommendationFeatureSnapshot.objects.filter(expires_at__lt=timezone.now() - timedelta(days=1)).delete()
    user_ids = sorted(
        {
            int(value)
            for value in (
                list(FavoriteProduct.objects.values_list("user_id", flat=True)[:user_limit])
                + list(RecentlyViewedProduct.objects.values_list("user_id", flat=True)[:user_limit])
                + list(OrderItem.objects.values_list("order__placed_by_id", flat=True)[:user_limit])
            )
            if value
        }
    )[:user_limit]
    product_ids = list(
        Product.objects.filter(publication_status=Product.PublicationStatus.PUBLISHED)
        .order_by("-id")
        .values_list("id", flat=True)[:product_limit]
    )
    user_rows = 0
    for user_id in user_ids:
        user_ref = type("UserRef", (), {"is_authenticated": True, "id": user_id})()
        _snapshot(
            RecommendationFeatureSnapshot.FeatureSet.USER_V1,
            RecommendationFeatureSnapshot.ScopeType.USER,
            user_id,
            payload=build_user_feature_payload(user_ref),
        )
        user_rows += 1
    product_rows = 0
    for product in Product.objects.filter(id__in=product_ids).only(
        "id", "brand_id", "category_id", "seller_id", "price", "is_new", "is_promo", "stock_qty", "lead_time_days", "min_order_qty"
    ):
        _snapshot(
            RecommendationFeatureSnapshot.FeatureSet.PRODUCT_V1,
            RecommendationFeatureSnapshot.ScopeType.PRODUCT,
            product.id,
            payload=build_product_feature_payload(product),
        )
        product_rows += 1
    _snapshot(
        RecommendationFeatureSnapshot.FeatureSet.GLOBAL_V1,
        RecommendationFeatureSnapshot.ScopeType.GLOBAL,
        0,
        payload=build_global_feature_payload(),
        expires_in_seconds=3 * 3600,
    )
    return {"users": user_rows, "products": product_rows}


def user_feature_payload(user) -> dict:
    user_id = getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None
    if not user_id:
        return build_user_feature_payload(user)
    snapshot = latest_feature_snapshot(
        feature_set=RecommendationFeatureSnapshot.FeatureSet.USER_V1,
        scope_type=RecommendationFeatureSnapshot.ScopeType.USER,
        scope_id=user_id,
    )
    return dict(getattr(snapshot, "payload", {}) or build_user_feature_payload(user))


def product_feature_payload(product: Product) -> dict:
    snapshot = latest_feature_snapshot(
        feature_set=RecommendationFeatureSnapshot.FeatureSet.PRODUCT_V1,
        scope_type=RecommendationFeatureSnapshot.ScopeType.PRODUCT,
        scope_id=product.id,
    )
    return dict(getattr(snapshot, "payload", {}) or build_product_feature_payload(product))
