from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable, Sequence


@dataclass
class RecommendationCandidate:
    product_id: int
    reason_codes: set[str] = field(default_factory=set)
    candidate_sources: set[str] = field(default_factory=set)
    score_hint: Decimal = field(default_factory=lambda: Decimal("0"))


def _normalize_product_id(value) -> int:
    """Internal helper for normalize product id."""
    try:
        product_id = int(value)
    except (TypeError, ValueError):
        return 0
    return product_id if product_id > 0 else 0


def _position_hint(position: int, total: int, weight: str | int | float | Decimal) -> Decimal:
    """Internal helper for position hint."""
    total_count = max(1, int(total or 0))
    normalized_weight = Decimal(str(weight or 0))
    raw = Decimal(str(max(1, total_count - max(0, position) + 1)))
    return (raw / Decimal(str(total_count))) * normalized_weight


def collect_candidate_map(
    groups: Iterable[tuple[str, Sequence[int], str, str | int | float | Decimal]],
    *,
    exclude: set[int] | None = None,
    limit: int = 0,
) -> dict[int, RecommendationCandidate]:
    """Handle collect candidate map."""
    candidate_map: dict[int, RecommendationCandidate] = {}
    blocked = set(exclude or set())
    for source_name, product_ids, reason_code, weight in groups:
        ids = list(product_ids or [])
        for position, value in enumerate(ids, start=1):
            product_id = _normalize_product_id(value)
            if not product_id or product_id in blocked:
                continue
            candidate = candidate_map.setdefault(product_id, RecommendationCandidate(product_id=product_id))
            if reason_code:
                candidate.reason_codes.add(str(reason_code))
            if source_name:
                candidate.candidate_sources.add(str(source_name))
            candidate.score_hint += _position_hint(position, len(ids), weight)
    if not limit:
        return candidate_map
    ranked_ids = sorted(
        candidate_map,
        key=lambda product_id: (
            -candidate_map[product_id].score_hint,
            product_id,
        ),
    )[:limit]
    return {product_id: candidate_map[product_id] for product_id in ranked_ids}


def candidate_ids(candidate_map: dict[int, RecommendationCandidate]) -> list[int]:
    """Handle candidate ids."""
    return [
        product_id
        for product_id in sorted(
            candidate_map,
            key=lambda value: (-candidate_map[value].score_hint, value),
        )
    ]


def trace_for_ids(candidate_map: dict[int, RecommendationCandidate], product_ids: Sequence[int]) -> dict[str, dict[int, list[str] | float]]:
    """Handle trace for ids."""
    reason_codes_by_product: dict[int, list[str]] = {}
    candidate_sources_by_product: dict[int, list[str]] = {}
    score_hint_by_product: dict[int, float] = {}
    for value in product_ids:
        product_id = _normalize_product_id(value)
        if not product_id:
            continue
        candidate = candidate_map.get(product_id)
        if candidate is None:
            continue
        reason_codes_by_product[product_id] = sorted(candidate.reason_codes)
        candidate_sources_by_product[product_id] = sorted(candidate.candidate_sources)
        score_hint_by_product[product_id] = float(candidate.score_hint)
    return {
        "reason_codes_by_product": reason_codes_by_product,
        "candidate_sources_by_product": candidate_sources_by_product,
        "score_hint_by_product": score_hint_by_product,
    }
