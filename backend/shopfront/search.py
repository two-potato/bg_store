import logging
from typing import List

import requests
from django.conf import settings

log = logging.getLogger("shopfront")


class ESSearchUnavailable(Exception):
    pass


def _es_url() -> str:
    return getattr(settings, "ES_URL", "http://es:9200").rstrip("/")


def _es_index() -> str:
    return getattr(settings, "ES_PRODUCTS_INDEX", "products")


def _es_timeout() -> float:
    return float(getattr(settings, "ES_TIMEOUT_SECONDS", 0.8))


def _es_search_ids(query: str, limit: int) -> List[int]:
    payload = {
        "size": limit,
        "query": {
            "bool": {
                "should": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": [
                                "name^6",
                                "sku^5",
                                "brand^4",
                                "category^3",
                                "country_of_origin^3",
                                "description^2",
                            ],
                            "type": "best_fields",
                            "operator": "and",
                            "fuzziness": "AUTO",
                        }
                    },
                    {"term": {"sku.keyword": {"value": query, "boost": 12}}},
                ],
                "minimum_should_match": 1,
            }
        },
    }
    url = f"{_es_url()}/{_es_index()}/_search"
    try:
        r = requests.post(url, json=payload, timeout=_es_timeout())
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        raise ESSearchUnavailable(str(exc)) from exc

    hits = data.get("hits", {}).get("hits", [])
    ids: List[int] = []
    for hit in hits:
        src = hit.get("_source") or {}
        raw_id = src.get("id", hit.get("_id"))
        try:
            pid = int(raw_id)
        except Exception:
            continue
        ids.append(pid)
    return ids


def search_product_ids(query: str, limit: int = 8) -> List[int]:
    try:
        ids = _es_search_ids(query=query, limit=limit)
        log.info("live_search_es_ok", extra={"query": query, "count": len(ids)})
        return ids
    except ESSearchUnavailable as exc:
        log.warning("live_search_es_unavailable", extra={"query": query, "reason": str(exc)})
        return []
