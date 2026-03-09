import logging
from hashlib import sha1
from typing import List, Tuple

import requests
from django.conf import settings
from django.core.cache import cache

log = logging.getLogger("shopfront")


class ESSearchUnavailable(Exception):
    pass


def _es_url() -> str:
    return getattr(settings, "ES_URL", "http://es:9200").rstrip("/")


def _es_index() -> str:
    return getattr(settings, "ES_PRODUCTS_INDEX", "products")


def _es_timeout() -> float:
    return float(getattr(settings, "ES_TIMEOUT_SECONDS", 0.8))


def _normalize_bundle(bundle):
    if isinstance(bundle, (list, tuple)) and len(bundle) == 3:
        ids, countries, suggestions = bundle
        return list(ids or []), list(countries or []), list(suggestions or [])
    if isinstance(bundle, (list, tuple)) and len(bundle) == 2:
        ids, countries = bundle
        return list(ids or []), list(countries or []), []
    return [], [], []


def _norm_query(query: str) -> str:
    return " ".join((query or "").strip().lower().split())


def _search_payload(query: str, limit: int, country_limit: int):
    norm_q = _norm_query(query)
    safe_country_limit = max(1, int(country_limit or 1))
    safe_limit = max(1, int(limit or 1))
    return {
        "size": safe_limit,
        "query": {
            "bool": {
                "should": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": [
                                "name^6",
                                "sku^5",
                                "manufacturer_sku^4",
                                "barcode^4",
                                "brand^4",
                                "series^3",
                                "store_name^4",
                                "seller_username^3",
                                "category^3",
                                "country_of_origin^3",
                                "tags^2",
                                "material^2",
                                "purpose^2",
                                "flavor^2",
                                "description^2",
                                "store_description^2",
                            ],
                            "type": "most_fields",
                            "operator": "or",
                            "fuzziness": "AUTO",
                        }
                    },
                    {"prefix": {"name": {"value": norm_q, "boost": 9}}},
                    {"prefix": {"brand": {"value": norm_q, "boost": 6}}},
                    {"prefix": {"category": {"value": norm_q, "boost": 6}}},
                    {"term": {"sku.keyword": {"value": query, "boost": 12}}},
                    {"term": {"manufacturer_sku.keyword": {"value": query, "boost": 10}}},
                    {"term": {"barcode.keyword": {"value": query, "boost": 10}}},
                ],
                "minimum_should_match": 1,
            }
        },
        "suggest": {
            "query_suggest": {
                "prefix": norm_q,
                "completion": {
                    "field": "suggest",
                    "size": max(6, min(10, safe_limit)),
                    "skip_duplicates": True,
                },
            }
        },
        "aggs": {
            "country_suggestions_scope": {
                "filter": {"prefix": {"country_of_origin_keyword": norm_q}},
                "aggs": {
                    "country_suggestions": {
                        "terms": {
                            "field": "country_of_origin.keyword",
                            "size": safe_country_limit,
                            "order": {"_count": "desc"},
                        }
                    }
                },
            }
        },
    }


def _es_search_bundle(query: str, limit: int, country_limit: int) -> Tuple[List[int], List[str], List[str]]:
    if not getattr(settings, "ES_ENABLED", True):
        raise ESSearchUnavailable("disabled")
    payload = _search_payload(query=query, limit=limit, country_limit=country_limit)
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

    buckets = (
        data.get("aggregations", {})
        .get("country_suggestions_scope", {})
        .get("country_suggestions", {})
        .get("buckets", [])
    )
    countries = [b.get("key", "") for b in buckets if b.get("key")]
    suggest_options = (
        data.get("suggest", {})
        .get("query_suggest", [])
    )
    suggestions: List[str] = []
    seen = set()
    for entry in suggest_options:
        for opt in entry.get("options", []):
            text = " ".join(str(opt.get("text", "")).strip().split())
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            suggestions.append(text)
    return ids, countries, suggestions


def live_search_bundle(query: str, limit: int = 8, country_limit: int = 6) -> Tuple[List[int], List[str], List[str]]:
    norm_q = _norm_query(query)
    cache_key = f"shopfront:es_live_bundle:v2:{sha1(f'{norm_q}:{limit}:{country_limit}'.encode('utf-8')).hexdigest()}"
    cached = cache.get(cache_key)
    if cached is not None:
        ids, countries, suggestions = cached
        return list(ids), list(countries), list(suggestions)

    ids, countries, suggestions = _es_search_bundle(query=query, limit=limit, country_limit=country_limit)
    if country_limit <= 0:
        countries = []
    cache.set(cache_key, [ids, countries, suggestions], timeout=getattr(settings, "CACHE_TTL_ES_SEARCH", 120))
    log.info(
        "live_search_es_ok",
        extra={"query": query, "count": len(ids), "country_count": len(countries), "suggestions_count": len(suggestions)},
    )
    return ids, countries, suggestions


def search_product_ids(query: str, limit: int = 8) -> List[int]:
    try:
        ids, _countries, _suggestions = _normalize_bundle(
            live_search_bundle(query=query, limit=limit, country_limit=0)
        )
        return ids
    except ESSearchUnavailable as exc:
        log.warning("live_search_es_unavailable", extra={"query": query, "reason": str(exc)})
        return []


def popular_country_suggestions(query: str, limit: int = 6) -> List[str]:
    try:
        _ids, countries, _suggestions = _normalize_bundle(
            live_search_bundle(query=query, limit=1, country_limit=limit)
        )
        return countries
    except ESSearchUnavailable as exc:
        log.warning("country_suggestions_es_unavailable", extra={"query": query, "reason": str(exc)})
        return []
