from __future__ import annotations

from django.db import models
from django.db.models import Count
from django.utils import timezone

from catalog.models import Product
from orders.models import OrderItem

from .models import (
    BrandSubscription,
    CategorySubscription,
    FavoriteProduct,
    RecommendationPopularitySnapshot,
    RecommendationProductAffinity,
    RecommendationReplenishmentProfile,
    RecommendationSet,
    RecommendationUserAffinity,
    RecentlyViewedProduct,
)
from .search_service import get_search_provider


def _user_id(user) -> int:
    value = getattr(user, "id", None) or getattr(user, "pk", None) or 0
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _dedupe_ids(values: list[int], *, exclude: set[int] | None = None, limit: int = 0) -> list[int]:
    seen = set(exclude or set())
    out: list[int] = []
    for value in values:
        try:
            pid = int(value)
        except (TypeError, ValueError):
            continue
        if pid <= 0 or pid in seen:
            continue
        seen.add(pid)
        out.append(pid)
        if limit and len(out) >= limit:
            break
    return out


def recommendation_set_ids(kind: str, *, scope_type: str, scope_id: int = 0, limit: int = 0) -> list[int]:
    now = timezone.now()
    row = (
        RecommendationSet.objects.filter(kind=kind, scope_type=scope_type, scope_id=scope_id)
        .filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now))
        .order_by("-generated_at", "-id")
        .first()
    )
    ids = list(getattr(row, "product_ids", []) or [])
    return _dedupe_ids(ids, limit=limit)


def popularity_snapshot_ids(*, scope_type: str = RecommendationPopularitySnapshot.ScopeType.GLOBAL, scope_id: int = 0, window: str = "7d", limit: int = 8) -> list[int]:
    rows = (
        RecommendationPopularitySnapshot.objects.filter(scope_type=scope_type, scope_id=scope_id, window=window)
        .order_by("-score", "product_id")
        .values_list("product_id", flat=True)[:limit]
    )
    return list(rows)


def product_affinity_ids(product: Product, *, affinity_type: str = RecommendationProductAffinity.AffinityType.CO_PURCHASE, limit: int = 8) -> list[int]:
    rows = (
        RecommendationProductAffinity.objects.filter(source_product_id=product.id, affinity_type=affinity_type)
        .order_by("-score", "-orders_count", "target_product_id")
        .values_list("target_product_id", flat=True)[:limit]
    )
    return list(rows)


def user_reorder_ids(user, *, limit: int = 8) -> list[int]:
    uid = _user_id(user)
    if not uid:
        return []
    rows = (
        OrderItem.objects.filter(order__placed_by_id=uid)
        .values("product_id")
        .annotate(orders_count=Count("order_id", distinct=True), qty_total=Count("id"))
        .order_by("-orders_count", "-qty_total", "product_id")[:limit]
    )
    return [row["product_id"] for row in rows]


def user_affinity_seed_ids(user, *, limit: int = 24) -> list[int]:
    uid = _user_id(user)
    if not uid:
        return []
    favorites_ids = list(
        FavoriteProduct.objects.filter(user_id=uid)
        .order_by("-created_at")
        .values_list("product_id", flat=True)[:limit]
    )
    recent_ids = list(
        RecentlyViewedProduct.objects.filter(user_id=uid)
        .order_by("-updated_at")
        .values_list("product_id", flat=True)[:limit]
    )
    return _dedupe_ids(favorites_ids + recent_ids, limit=limit)


def personalized_candidate_ids(user, *, limit: int = 48) -> list[int]:
    uid = _user_id(user)
    if not uid:
        return []
    seed_ids = user_affinity_seed_ids(user, limit=max(24, limit))
    affinity_ids = hybrid_affinity_candidates(user, limit=max(limit, 24))
    if not seed_ids and not affinity_ids:
        return []
    products = Product.objects.filter(id__in=seed_ids).select_related("brand", "category")
    brand_ids = {product.brand_id for product in products if product.brand_id}
    category_ids = {product.category_id for product in products if product.category_id}
    ids = list(
        Product.objects.filter(models.Q(brand_id__in=brand_ids) | models.Q(category_id__in=category_ids))
        .exclude(id__in=seed_ids)
        .order_by("-is_promo", "-is_new", "name")
        .values_list("id", flat=True)[: limit * 2]
    )
    return _dedupe_ids(affinity_ids + ids, limit=limit)


def watchlist_candidate_ids(user, *, limit: int = 16) -> list[int]:
    uid = _user_id(user)
    if not uid:
        return []
    brand_ids = BrandSubscription.objects.filter(user_id=uid).values_list("brand_id", flat=True)
    category_ids = CategorySubscription.objects.filter(user_id=uid).values_list("category_id", flat=True)
    ids = list(
        Product.objects.filter(models.Q(brand_id__in=brand_ids) | models.Q(category_id__in=category_ids))
        .order_by("-is_new", "-is_promo", "name")
        .values_list("id", flat=True)[: limit * 2]
    )
    return _dedupe_ids(ids, limit=limit)


def seller_cross_sell_candidate_ids(product: Product, *, limit: int = 8) -> list[int]:
    if not product.seller_id:
        return []
    qs = Product.objects.filter(seller_id=product.seller_id).exclude(id=product.id)
    if product.category_id:
        qs = qs.exclude(category_id=product.category_id)
    return list(qs.order_by("-is_promo", "-is_new", "name").values_list("id", flat=True)[:limit])


def opensearch_similar_products(product: Product, *, limit: int = 12) -> list[int]:
    query_parts = [
        getattr(product, "name", ""),
        getattr(getattr(product, "brand", None), "name", "") or "",
        getattr(getattr(product, "category", None), "name", "") or "",
        getattr(product, "material", "") or "",
        getattr(product, "purpose", "") or "",
    ]
    query = " ".join(part for part in query_parts if part).strip()
    if not query:
        return []
    bundle = get_search_provider(prefer_semantic=True).live_bundle(query=query, limit=limit + 4, country_limit=0)
    return _dedupe_ids(bundle.product_ids, exclude={product.id}, limit=limit)


def opensearch_substitute_products(product: Product, *, limit: int = 12) -> list[int]:
    query_parts = [
        getattr(getattr(product, "category", None), "name", "") or "",
        getattr(product, "material", "") or "",
        getattr(product, "purpose", "") or "",
    ]
    query = " ".join(part for part in query_parts if part).strip() or getattr(product, "name", "")
    bundle = get_search_provider(prefer_semantic=True).live_bundle(query=query, limit=limit + 8, country_limit=0)
    return _dedupe_ids(bundle.product_ids, exclude={product.id}, limit=limit)


def search_recovery_candidate_ids(query: str, *, limit: int = 12) -> list[int]:
    bundle = get_search_provider(prefer_semantic=True).live_bundle(query=query, limit=limit, country_limit=0)
    return _dedupe_ids(bundle.product_ids, limit=limit)


def user_affinity_profile(user, *, limit_per_dimension: int = 6) -> dict[str, list]:
    uid = _user_id(user)
    if not uid:
        return {"brand": [], "category": [], "seller": [], "tag": [], "price_band": []}
    rows = list(
        RecommendationUserAffinity.objects.filter(user_id=uid)
        .order_by("dimension", "-score", "-event_count", "entity_id", "entity_key")
    )
    profile: dict[str, list] = {"brand": [], "category": [], "seller": [], "tag": [], "price_band": []}
    per_dimension: dict[str, int] = {}
    for row in rows:
        dimension = str(row.dimension)
        count = per_dimension.get(dimension, 0)
        if count >= limit_per_dimension:
            continue
        profile.setdefault(dimension, []).append(row)
        per_dimension[dimension] = count + 1
    return profile


def hybrid_affinity_candidates(user, *, limit: int = 24) -> list[int]:
    uid = _user_id(user)
    if not uid:
        return []
    profile = user_affinity_profile(user, limit_per_dimension=max(4, limit))
    brand_ids = [row.entity_id for row in profile.get("brand", []) if row.entity_id]
    category_ids = [row.entity_id for row in profile.get("category", []) if row.entity_id]
    seller_ids = [row.entity_id for row in profile.get("seller", []) if row.entity_id]
    tag_ids = [row.entity_id for row in profile.get("tag", []) if row.entity_id]
    price_bands = [row.entity_key for row in profile.get("price_band", []) if row.entity_key]
    q = models.Q()
    if brand_ids:
        q |= models.Q(brand_id__in=brand_ids)
    if category_ids:
        q |= models.Q(category_id__in=category_ids)
    if seller_ids:
        q |= models.Q(seller_id__in=seller_ids)
    if tag_ids:
        q |= models.Q(tags__id__in=tag_ids)
    if not (brand_ids or category_ids or seller_ids or tag_ids or price_bands):
        return []
    qs = Product.objects.filter(publication_status=Product.PublicationStatus.PUBLISHED)
    if q:
        qs = qs.filter(q)
    if price_bands:
        price_q = models.Q()
        for band in price_bands:
            if band == "entry":
                price_q |= models.Q(price__lt=2000)
            elif band == "mid":
                price_q |= models.Q(price__gte=2000, price__lt=10000)
            elif band == "premium":
                price_q |= models.Q(price__gte=10000)
        qs = qs.filter(price_q)
    ids = list(
        qs.order_by("-is_promo", "-is_new", "name")
        .distinct()
        .values_list("id", flat=True)[: limit * 3]
    )
    return _dedupe_ids(ids, limit=limit)


def user_replenishment_ids(user, *, limit: int = 8) -> list[int]:
    uid = _user_id(user)
    if not uid:
        return []
    return list(
        RecommendationReplenishmentProfile.objects.filter(user_id=uid)
        .order_by("-score", "product_id")
        .values_list("product_id", flat=True)[:limit]
    )
