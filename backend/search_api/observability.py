"""Search observability helpers for logs and Prometheus metrics.

These helpers keep search quality signals explicit without coupling views to the
metrics backend. Structured logs flow into Loki, and Prometheus metrics are
exposed through the existing `/metrics` endpoint for Grafana dashboards.
"""

from __future__ import annotations

from typing import Iterable
from decimal import Decimal

from prometheus_client import Counter, Histogram


SEARCH_REQUESTS_TOTAL = Counter(
    "servio_search_requests_total",
    "Count search requests by UI surface, provider, and outcome.",
    ["surface", "provider", "outcome"],
)

SEARCH_ZERO_RESULTS_TOTAL = Counter(
    "servio_search_zero_results_total",
    "Count zero-result search responses by UI surface and provider.",
    ["surface", "provider"],
)

SEARCH_REWRITES_TOTAL = Counter(
    "servio_search_rewrites_total",
    "Count search query rewrites by UI surface and rewrite kind.",
    ["surface", "rewrite_kind"],
)

SEARCH_LATENCY_SECONDS = Histogram(
    "servio_search_latency_seconds",
    "Search execution latency by UI surface and provider.",
    ["surface", "provider"],
    buckets=(0.01, 0.03, 0.05, 0.1, 0.2, 0.35, 0.5, 0.8, 1.2, 2.0, 3.0),
)

SEARCH_FEEDBACK_EVENTS_TOTAL = Counter(
    "servio_search_feedback_events_total",
    "Count first-party search feedback events by event name, surface, and origin.",
    ["event_name", "surface", "origin"],
)

SEARCH_ATTRIBUTED_ORDERS_TOTAL = Counter(
    "servio_search_attributed_orders_total",
    "Count orders attributed to search by source channel and origin.",
    ["source_channel", "origin"],
)

SEARCH_ATTRIBUTED_REVENUE_TOTAL = Counter(
    "servio_search_attributed_revenue_total",
    "Total attributed order revenue from search by source channel and origin.",
    ["source_channel", "origin"],
)


def observe_search_rewrite(*, surface: str, rewrite_kind: str, logger, original_query: str, effective_query: str, rewritten_query: str) -> None:
    """Emit rewrite metrics and a structured log for query normalization."""
    if not rewrite_kind:
        return
    SEARCH_REWRITES_TOTAL.labels(surface=surface, rewrite_kind=rewrite_kind).inc()
    logger.info(
        "search_query_rewritten",
        extra={
            "ui_surface": surface,
            "rewrite_kind": rewrite_kind,
            "original_query": original_query,
            "effective_query": effective_query,
            "rewritten_query": rewritten_query,
        },
    )


def observe_search_response(
    *,
    surface: str,
    provider: str,
    query: str,
    effective_query: str,
    rewritten_query: str,
    rewrite_kind: str,
    duration_seconds: float,
    result_count: int,
    suggestions_count: int,
    countries_count: int = 0,
    top_product_ids: Iterable[int] | None = None,
    logger,
) -> None:
    """Record a search response for metrics and Loki-friendly structured logs."""
    outcome = "ok" if result_count > 0 else "zero_results"
    SEARCH_REQUESTS_TOTAL.labels(surface=surface, provider=provider, outcome=outcome).inc()
    SEARCH_LATENCY_SECONDS.labels(surface=surface, provider=provider).observe(duration_seconds)
    if result_count == 0:
        SEARCH_ZERO_RESULTS_TOTAL.labels(surface=surface, provider=provider).inc()
    logger.info(
        "search_response_ready",
        extra={
            "ui_surface": surface,
            "provider": provider,
            "query": query,
            "effective_query": effective_query,
            "rewritten_query": rewritten_query,
            "rewrite_kind": rewrite_kind,
            "duration_ms": round(duration_seconds * 1000, 2),
            "result_count": result_count,
            "country_count": countries_count,
            "suggestions_count": suggestions_count,
            "top_product_ids": list(top_product_ids or [])[:12],
        },
    )
    if result_count == 0:
        logger.warning(
            "search_zero_results",
            extra={
                "ui_surface": surface,
                "provider": provider,
                "query": query,
                "effective_query": effective_query,
                "rewritten_query": rewritten_query,
                "rewrite_kind": rewrite_kind,
                "suggestions_count": suggestions_count,
            },
        )


def observe_search_feedback_event(
    *,
    event_name: str,
    surface: str,
    origin: str,
    search_term: str,
    item_id: str,
    item_name: str,
    position: int,
    results_count: int,
    provider: str,
    rewrite_kind: str,
    logger,
) -> None:
    """Record search feedback events emitted from the frontend."""
    safe_origin = origin or "unknown"
    safe_surface = surface or "unknown"
    SEARCH_FEEDBACK_EVENTS_TOTAL.labels(
        event_name=event_name or "unknown",
        surface=safe_surface,
        origin=safe_origin,
    ).inc()
    logger.info(
        "search_feedback_event",
        extra={
            "ui_surface": safe_surface,
            "event_name": event_name,
            "search_origin": safe_origin,
            "search_term": search_term,
            "item_id": item_id,
            "item_name": item_name,
            "position": int(position or 0),
            "results_count": int(results_count or 0),
            "provider": provider or "",
            "rewrite_kind": rewrite_kind or "",
        },
    )


def observe_search_order_attribution(*, order, attribution: dict, logger) -> None:
    """Record order-level search attribution for conversion reporting."""
    if not attribution:
        return
    items = list(attribution.get("items") or [])
    origins = sorted({str(item.get("search_origin") or "unknown") for item in items}) or ["unknown"]
    attributed_item_count = int(attribution.get("attributed_item_count") or 0)
    order_total = Decimal(str(getattr(order, "total", 0) or 0))
    revenue_slice = (order_total / max(1, len(origins))) if order_total > 0 else Decimal("0")
    for origin in origins:
        SEARCH_ATTRIBUTED_ORDERS_TOTAL.labels(
            source_channel=getattr(order, "source_channel", "") or "unknown",
            origin=origin,
        ).inc()
        if revenue_slice > 0:
            SEARCH_ATTRIBUTED_REVENUE_TOTAL.labels(
                source_channel=getattr(order, "source_channel", "") or "unknown",
                origin=origin,
            ).inc(float(revenue_slice))
    logger.info(
        "search_order_attributed",
        extra={
            "order_id": order.id,
            "source_channel": getattr(order, "source_channel", ""),
            "order_total": float(order_total),
            "attributed_item_count": attributed_item_count,
            "attributed_queries": list(attribution.get("attributed_queries") or [])[:8],
            "origins": origins,
        },
    )
