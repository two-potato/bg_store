from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
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


@dataclass
class RankedRecommendationResult:
    product_ids: list[int]
    scores_by_product: dict[int, float]
    reason_codes_by_product: dict[int, list[str]]
    candidate_sources_by_product: dict[int, list[str]]
    metadata: dict[str, object] = field(default_factory=dict)


def _user_affinity(user) -> dict[str, set[int]]:
    user_id = getattr(user, "id", None) or getattr(user, "pk", None)
    if not getattr(user, "is_authenticated", False) or not user_id:
        return {"brands": set(), "categories": set(), "favorites": set(), "recent": set()}
    favorite_ids = set(FavoriteProduct.objects.filter(user_id=user_id).values_list("product_id", flat=True)[:128])
    recent_ids = set(RecentlyViewedProduct.objects.filter(user_id=user_id).values_list("product_id", flat=True)[:128])
    brands = set(BrandSubscription.objects.filter(user_id=user_id).values_list("brand_id", flat=True))
    categories = set(CategorySubscription.objects.filter(user_id=user_id).values_list("category_id", flat=True))
    return {"brands": brands, "categories": categories, "favorites": favorite_ids, "recent": recent_ids}


def select_ranked_product_ids(
    ordered_candidate_ids: list[int],
    *,
    products_by_id: dict[int, Product],
    blocked_product_ids: set[int] | None = None,
    require_in_stock: bool = False,
    max_per_seller: int | None = None,
    max_per_brand: int | None = None,
    max_per_category: int | None = None,
    limit: int = 8,
) -> list[int]:
    blocked_ids = set(blocked_product_ids or set())
    seller_limit = max(1, int(max_per_seller)) if max_per_seller is not None else None
    brand_limit = max(1, int(max_per_brand)) if max_per_brand is not None else None
    category_limit = max(1, int(max_per_category)) if max_per_category is not None else None
    selected: list[int] = []
    seller_counts: Counter[int] = Counter()
    brand_counts: Counter[int] = Counter()
    category_counts: Counter[int] = Counter()
    for product_id in ordered_candidate_ids:
        product = products_by_id.get(product_id)
        if product is None or product_id in blocked_ids:
            continue
        if require_in_stock and product.display_stock_qty <= 0:
            continue
        seller_id = int(getattr(product, "seller_id", 0) or 0)
        brand_id = int(getattr(product, "brand_id", 0) or 0)
        category_id = int(getattr(product, "category_id", 0) or 0)
        if seller_limit is not None and seller_id and seller_counts[seller_id] >= seller_limit:
            continue
        if brand_limit is not None and brand_id and brand_counts[brand_id] >= brand_limit:
            continue
        if category_limit is not None and category_id and category_counts[category_id] >= category_limit:
            continue
        selected.append(product_id)
        if seller_id:
            seller_counts[seller_id] += 1
        if brand_id:
            brand_counts[brand_id] += 1
        if category_id:
            category_counts[category_id] += 1
        if len(selected) >= limit:
            return selected
    if len(selected) < min(limit, len(ordered_candidate_ids)):
        for product_id in ordered_candidate_ids:
            product = products_by_id.get(product_id)
            if product is None or product_id in selected or product_id in blocked_ids:
                continue
            if require_in_stock and product.display_stock_qty <= 0:
                continue
            selected.append(product_id)
            if len(selected) >= limit:
                break
    return selected[:limit]


def rank_recommendation_candidates(
    candidate_ids: list[int],
    *,
    user=None,
    source_product: Product | None = None,
    cart_product_ids: set[int] | None = None,
    source_name: str = "",
    experiment_variant: str = "control",
    candidate_reason_codes: dict[int, list[str] | set[str] | tuple[str, ...]] | None = None,
    candidate_sources: dict[int, list[str] | set[str] | tuple[str, ...]] | None = None,
    blocked_product_ids: set[int] | None = None,
    require_in_stock: bool = False,
    max_per_seller: int | None = None,
    max_per_brand: int | None = None,
    max_per_category: int | None = None,
    limit: int = 8,
) -> RankedRecommendationResult:
    if not candidate_ids:
        return RankedRecommendationResult(
            product_ids=[],
            scores_by_product={},
            reason_codes_by_product={},
            candidate_sources_by_product={},
            metadata={"strategy": "heuristic_ranked", "model_version": ""},
        )
    affinity = _user_affinity(user)
    cart_ids = set(cart_product_ids or set())
    blocked_ids = set(blocked_product_ids or set())
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

    candidate_reason_codes = candidate_reason_codes or {}
    candidate_sources = candidate_sources or {}

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
        reasons = {str(value) for value in (candidate_reason_codes.get(product.id) or []) if str(value).strip()}
        sources = {str(value) for value in (candidate_sources.get(product.id) or []) if str(value).strip()}
        if "co_purchase" in reasons:
            score += Decimal("3")
        if "replenishment_due" in reasons:
            score += Decimal("2.5")
        if "user_affinity" in reasons:
            score += Decimal("2")
        if "watchlist_match" in reasons:
            score += Decimal("1.5")
        if "trending" in reasons:
            score += Decimal("1")
        if len(sources) >= 2:
            score += Decimal("1.5")
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

    scores_by_product = {product.id: _score(product) for product in products.values()}
    ranked = sorted(products.values(), key=lambda product: (-scores_by_product[product.id], candidate_ids.index(product.id), product.id))
    seller_limit = 3 if experiment_variant == "control" else 2
    if max_per_seller is not None:
        seller_limit = max(1, int(max_per_seller))
    selected = select_ranked_product_ids(
        [product.id for product in ranked],
        products_by_id=products,
        blocked_product_ids=blocked_ids,
        require_in_stock=require_in_stock,
        max_per_seller=seller_limit,
        max_per_brand=max_per_brand,
        max_per_category=max_per_category,
        limit=limit,
    )
    return RankedRecommendationResult(
        product_ids=selected,
        scores_by_product={product_id: float(scores_by_product[product_id]) for product_id in selected if product_id in scores_by_product},
        reason_codes_by_product={
            product_id: sorted({str(value) for value in (candidate_reason_codes.get(product_id) or []) if str(value).strip()})
            for product_id in selected
        },
        candidate_sources_by_product={
            product_id: sorted({str(value) for value in (candidate_sources.get(product_id) or []) if str(value).strip()})
            for product_id in selected
        },
        metadata={"strategy": "heuristic_ranked", "model_version": ""},
    )


def rerank_product_ids(
    candidate_ids: list[int],
    *,
    user=None,
    source_product: Product | None = None,
    cart_product_ids: set[int] | None = None,
    source_name: str = "",
    experiment_variant: str = "control",
    candidate_reason_codes: dict[int, list[str] | set[str] | tuple[str, ...]] | None = None,
    candidate_sources: dict[int, list[str] | set[str] | tuple[str, ...]] | None = None,
    blocked_product_ids: set[int] | None = None,
    require_in_stock: bool = False,
    max_per_seller: int | None = None,
    max_per_brand: int | None = None,
    max_per_category: int | None = None,
    limit: int = 8,
) -> list[int]:
    return rank_recommendation_candidates(
        candidate_ids,
        user=user,
        source_product=source_product,
        cart_product_ids=cart_product_ids,
        source_name=source_name,
        experiment_variant=experiment_variant,
        candidate_reason_codes=candidate_reason_codes,
        candidate_sources=candidate_sources,
        blocked_product_ids=blocked_product_ids,
        require_in_stock=require_in_stock,
        max_per_seller=max_per_seller,
        max_per_brand=max_per_brand,
        max_per_category=max_per_category,
        limit=limit,
    ).product_ids
