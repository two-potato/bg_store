from __future__ import annotations

from collections import Counter
from decimal import Decimal

from catalog.models import Product

from .models import (
    BrandSubscription,
    CategorySubscription,
    FavoriteProduct,
    RecommendationEvent,
    RecommendationReplenishmentProfile,
    RecommendationUserAffinity,
    RecentlyViewedProduct,
)


def _user_affinity(user) -> dict[str, set[int]]:
    user_id = getattr(user, "id", None) or getattr(user, "pk", None)
    if not getattr(user, "is_authenticated", False) or not user_id:
        return {"brands": set(), "categories": set(), "favorites": set(), "recent": set()}
    favorite_ids = set(FavoriteProduct.objects.filter(user_id=user_id).values_list("product_id", flat=True)[:128])
    recent_ids = set(RecentlyViewedProduct.objects.filter(user_id=user_id).values_list("product_id", flat=True)[:128])
    brands = set(BrandSubscription.objects.filter(user_id=user_id).values_list("brand_id", flat=True))
    categories = set(CategorySubscription.objects.filter(user_id=user_id).values_list("category_id", flat=True))
    return {"brands": brands, "categories": categories, "favorites": favorite_ids, "recent": recent_ids}


def rerank_product_ids(
    candidate_ids: list[int],
    *,
    user=None,
    source_product: Product | None = None,
    cart_product_ids: set[int] | None = None,
    source_name: str = "",
    experiment_variant: str = "control",
    limit: int = 8,
) -> list[int]:
    if not candidate_ids:
        return []
    affinity = _user_affinity(user)
    cart_ids = set(cart_product_ids or set())
    products = {
        product.id: product
        for product in Product.objects.filter(id__in=candidate_ids).select_related("brand", "category", "seller")
    }
    source_brand_id = getattr(source_product, "brand_id", None)
    source_category_id = getattr(source_product, "category_id", None)
    source_seller_id = getattr(source_product, "seller_id", None)
    base_bonus = Counter({pid: max(0, len(candidate_ids) - pos) for pos, pid in enumerate(candidate_ids)})
    user_id = getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None
    recent_impressions = Counter()
    explicit_affinities: dict[tuple[str, int], Decimal] = {}
    replenishment_scores: dict[int, Decimal] = {}
    if user_id:
        recent_impressions = Counter(
            RecommendationEvent.objects.filter(
                user_id=user_id,
                event="recommendation_impression",
            ).values_list("product_id", flat=True)[:256]
        )
        for row in RecommendationUserAffinity.objects.filter(user_id=user_id).only("dimension", "entity_id", "score"):
            explicit_affinities[(str(row.dimension), int(row.entity_id or 0))] = Decimal(str(row.score or 0))
        for row in RecommendationReplenishmentProfile.objects.filter(user_id=user_id, product_id__in=candidate_ids).only("product_id", "score"):
            replenishment_scores[int(row.product_id)] = Decimal(str(row.score or 0))

    def _score(product: Product) -> Decimal:
        score = Decimal("0")
        normalization = Decimal(str(max(1, len(candidate_ids))))
        score += Decimal(base_bonus.get(product.id, 0)) / normalization * Decimal("10")
        if product.id in affinity["favorites"]:
            score += Decimal("6")
        if product.id in affinity["recent"]:
            score += Decimal("3")
        if product.brand_id and product.brand_id in affinity["brands"]:
            score += Decimal("4")
        if product.category_id and product.category_id in affinity["categories"]:
            score += Decimal("5")
        score += explicit_affinities.get(("brand", int(product.brand_id or 0)), Decimal("0")) * Decimal("0.6")
        score += explicit_affinities.get(("category", int(product.category_id or 0)), Decimal("0")) * Decimal("0.8")
        score += explicit_affinities.get(("seller", int(product.seller_id or 0)), Decimal("0")) * Decimal("0.5")
        if product.is_promo:
            score += Decimal("1.5")
        if product.is_new:
            score += Decimal("1")
        if product.display_stock_qty > 0:
            score += Decimal("2")
        if product.display_lead_time_days <= 3:
            score += Decimal("1")
        if product.display_min_order_qty <= 5:
            score += Decimal("1")
        if source_brand_id and product.brand_id == source_brand_id:
            score += Decimal("2")
        if source_category_id and product.category_id == source_category_id:
            score += Decimal("3")
        if source_seller_id and product.seller_id == source_seller_id:
            score += Decimal("2")
        if source_name.endswith("substitute") or source_name.endswith("substitutes"):
            source_price = Decimal(str(getattr(source_product, "display_price", getattr(source_product, "price", 0)) or 0))
            product_price = Decimal(str(getattr(product, "display_price", getattr(product, "price", 0)) or 0))
            if source_price > 0 and product_price > 0:
                distance = abs(product_price - source_price) / source_price
                score += max(Decimal("0"), Decimal("4") - Decimal(str(distance)) * Decimal("4"))
        if source_name == "reorder":
            score += replenishment_scores.get(product.id, Decimal("0")) * Decimal("1.2")
        overshow_penalty = min(Decimal("6"), Decimal(str(recent_impressions.get(product.id, 0))) * Decimal("0.75"))
        score -= overshow_penalty
        if cart_ids and product.id in cart_ids:
            score -= Decimal("100")
        if experiment_variant == "ranked_v2":
            if product.display_stock_qty <= 0:
                score -= Decimal("20")
            if product.display_lead_time_days <= 2:
                score += Decimal("1.5")
        return score

    ranked = sorted(products.values(), key=lambda product: (-_score(product), candidate_ids.index(product.id), product.id))
    selected: list[int] = []
    seller_counts: Counter[int] = Counter()
    max_per_seller = 3 if experiment_variant == "control" else 2
    for product in ranked:
        seller_id = int(getattr(product, "seller_id", 0) or 0)
        if seller_id and seller_counts[seller_id] >= max_per_seller:
            continue
        selected.append(product.id)
        if seller_id:
            seller_counts[seller_id] += 1
        if len(selected) >= limit:
            break
    if len(selected) < min(limit, len(ranked)):
        for product in ranked:
            if product.id in selected:
                continue
            selected.append(product.id)
            if len(selected) >= limit:
                break
    return selected[:limit]
