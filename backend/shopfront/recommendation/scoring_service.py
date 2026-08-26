from __future__ import annotations

from dataclasses import dataclass

from catalog.models import Product

from .ml import active_model_for_surface, score_candidates_with_model
from .ranker import RankedRecommendationResult, rank_recommendation_candidates


@dataclass
class RecommendationScoringContract:
    surface: str
    variant: str
    strategy: str
    model_version: str


def score_candidates_contract(
    *,
    surface: str,
    candidate_ids: list[int],
    user,
    request,
    source_product: Product | None = None,
    cart_product_ids: set[int] | None = None,
    source_name: str = "",
    experiment_variant: str = "control",
    candidate_reason_codes: dict[int, list[str] | set[str] | tuple[str, ...]] | None = None,
    candidate_sources: dict[int, list[str] | set[str] | tuple[str, ...]] | None = None,
    blocked_product_ids: set[int] | None = None,
    limit: int = 8,
) -> tuple[RankedRecommendationResult, RecommendationScoringContract]:
    """Score candidates contract."""
    if experiment_variant == "ml_v1":
        model = active_model_for_surface(surface, variant="ml_v1")
        if model is not None:
            result = score_candidates_with_model(
                surface=surface,
                model=model,
                candidate_ids=candidate_ids,
                user=user,
                request=request,
                source_product=source_product,
                cart_product_ids=cart_product_ids,
                candidate_reason_codes=candidate_reason_codes,
                candidate_sources=candidate_sources,
                blocked_product_ids=blocked_product_ids,
                limit=limit,
            )
            return result, RecommendationScoringContract(
                surface=surface,
                variant=experiment_variant,
                strategy="ml_ranked",
                model_version=model.version,
            )
    result = rank_recommendation_candidates(
        candidate_ids,
        user=user,
        source_product=source_product,
        cart_product_ids=cart_product_ids,
        source_name=source_name,
        experiment_variant=experiment_variant,
        candidate_reason_codes=candidate_reason_codes,
        candidate_sources=candidate_sources,
        blocked_product_ids=blocked_product_ids,
        require_in_stock=source_name not in {"product_substitutes"},
        max_per_seller=2 if surface in {"home", "catalog", "checkout"} else 3,
        max_per_brand=2 if surface in {"home", "catalog"} else None,
        max_per_category=3 if surface in {"home", "catalog"} else None,
        limit=limit,
    )
    return result, RecommendationScoringContract(
        surface=surface,
        variant=experiment_variant,
        strategy="heuristic_ranked",
        model_version="",
    )
