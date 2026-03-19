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
) -> str:
    if not products:
        return ""
    payload = {
        "event": "recommendation_impression",
        "recommendation_source": source,
        "surface": surface or "",
        "experiment_variant": experiment_variant or "",
        "request_id": request_id or "",
        "ecommerce": {
            "item_list_name": source,
            "items": [tracking_item_from_product(product) for product in products[:12]],
        },
    }
    return json.dumps(payload, ensure_ascii=False)
