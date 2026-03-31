"""Recommendation observability helpers for metrics and structured logs."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from prometheus_client import Counter, Histogram


RECOMMENDATION_SELECTIONS_TOTAL = Counter(
    "servio_recommendation_selections_total",
    "Count recommendation selection executions by surface, source, and experiment variant.",
    ["surface", "source", "variant"],
)

RECOMMENDATION_CANDIDATE_COUNT = Histogram(
    "servio_recommendation_candidate_count",
    "Distribution of recommendation candidate counts before ranking.",
    ["surface", "source", "variant"],
    buckets=(0, 1, 2, 4, 8, 12, 20, 32, 48, 64),
)

RECOMMENDATION_EVENTS_TOTAL = Counter(
    "servio_recommendation_events_total",
    "Count first-party recommendation events by event, surface, source, and variant.",
    ["event_name", "surface", "source", "variant"],
)

RECOMMENDATION_ATTRIBUTED_ORDERS_TOTAL = Counter(
    "servio_recommendation_attributed_orders_total",
    "Count orders attributed to recommendations by source and variant.",
    ["source", "variant"],
)

RECOMMENDATION_ATTRIBUTED_REVENUE_TOTAL = Counter(
    "servio_recommendation_attributed_revenue_total",
    "Revenue attributed to recommendations by source and variant.",
    ["source", "variant"],
)


def observe_recommendation_selection(
    *,
    surface: str,
    source: str,
    variant: str,
    strategy: str,
    candidate_count: int,
    product_ids: Iterable[int],
    logger,
) -> None:
    """Observe recommendation selection."""
    safe_surface = surface or "unknown"
    safe_source = source or "unknown"
    safe_variant = variant or "control"
    RECOMMENDATION_SELECTIONS_TOTAL.labels(
        surface=safe_surface,
        source=safe_source,
        variant=safe_variant,
    ).inc()
    RECOMMENDATION_CANDIDATE_COUNT.labels(
        surface=safe_surface,
        source=safe_source,
        variant=safe_variant,
    ).observe(max(0, int(candidate_count or 0)))
    logger.info(
        "recommendation_selection_ready",
        extra={
            "ui_surface": safe_surface,
            "recommendation_source": safe_source,
            "experiment_variant": safe_variant,
            "strategy": strategy,
            "candidate_count": int(candidate_count or 0),
            "selected_product_ids": list(product_ids or [])[:16],
        },
    )


def observe_recommendation_event(
    *,
    event_name: str,
    surface: str,
    source: str,
    variant: str,
    product_id: int | str | None,
    position: int = 0,
    request_id: str = "",
    logger,
) -> None:
    """Observe recommendation event."""
    safe_surface = surface or "unknown"
    safe_source = source or "unknown"
    safe_variant = variant or "control"
    RECOMMENDATION_EVENTS_TOTAL.labels(
        event_name=event_name or "unknown",
        surface=safe_surface,
        source=safe_source,
        variant=safe_variant,
    ).inc()
    logger.info(
        "recommendation_feedback_event",
        extra={
            "ui_surface": safe_surface,
            "event_name": event_name,
            "recommendation_source": safe_source,
            "experiment_variant": safe_variant,
            "product_id": str(product_id or ""),
            "position": int(position or 0),
            "request_id": request_id or "",
        },
    )


def observe_recommendation_order_attribution(*, order, attribution: dict, logger) -> None:
    """Observe recommendation order attribution."""
    if not attribution:
        return
    items = list(attribution.get("items") or [])
    by_source: dict[tuple[str, str], list[dict]] = {}
    for item in items:
        key = (
            str(item.get("recommendation_source") or "unknown"),
            str(item.get("experiment_variant") or "control"),
        )
        by_source.setdefault(key, []).append(item)
    order_total = Decimal(str(getattr(order, "total", 0) or 0))
    revenue_slice = (order_total / max(1, len(by_source))) if order_total > 0 else Decimal("0")
    for (source, variant), grouped in by_source.items():
        RECOMMENDATION_ATTRIBUTED_ORDERS_TOTAL.labels(source=source, variant=variant).inc()
        if revenue_slice > 0:
            RECOMMENDATION_ATTRIBUTED_REVENUE_TOTAL.labels(source=source, variant=variant).inc(float(revenue_slice))
        logger.info(
            "recommendation_order_attributed",
            extra={
                "order_id": order.id,
                "recommendation_source": source,
                "experiment_variant": variant,
                "attributed_item_count": len(grouped),
                "order_total": float(order_total),
                "product_ids": [str(item.get("product_id") or "") for item in grouped][:16],
            },
        )
