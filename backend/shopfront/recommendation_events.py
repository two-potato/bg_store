from __future__ import annotations

import json

from .checkout_support import tracking_item_from_product


def recommendation_impression_payload(
    source: str,
    products,
    *,
    surface: str = "",
    experiment_variant: str = "",
    request_id: str = "",
    strategy: str = "",
    model_version: str = "",
    trace: dict | None = None,
) -> str:
    if not products:
        return ""
    trace = trace or {}
    reason_codes_by_product = trace.get("reason_codes_by_product") or {}
    candidate_sources_by_product = trace.get("candidate_sources_by_product") or {}
    score_hint_by_product = trace.get("score_hint_by_product") or {}
    items = []
    for product in products[:12]:
        item = tracking_item_from_product(product)
        product_id = getattr(product, "id", None)
        if product_id in reason_codes_by_product:
            item["recommendation_reason_codes"] = list(reason_codes_by_product.get(product_id) or [])
        if product_id in candidate_sources_by_product:
            item["recommendation_candidate_sources"] = list(candidate_sources_by_product.get(product_id) or [])
        if product_id in score_hint_by_product:
            item["recommendation_score_hint"] = score_hint_by_product.get(product_id)
        items.append(item)
    payload = {
        "event": "recommendation_impression",
        "recommendation_source": source,
        "surface": surface or "",
        "experiment_variant": experiment_variant or "",
        "request_id": request_id or "",
        "strategy": strategy or "",
        "model_version": model_version or "",
        "ecommerce": {
            "item_list_name": source,
            "items": items,
        },
    }
    return json.dumps(payload, ensure_ascii=False)
