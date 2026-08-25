from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, HTTPException, Query

SERVICE_NAME = os.getenv("SERVICE_NAME", "search-api")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")

SEMANTIC_QUERY_REWRITES = {
    "одноразка": "одноразовая посуда",
    "хозка": "расходные материалы",
    "барный сироп": "сироп для бара",
    "кофе для эспрессо": "зерновой кофе эспрессо",
    "упаковка на вынос": "takeaway упаковка",
}
SEARCH_SYNONYMS = {
    "сиропы": "сироп",
    "стаканы": "стакан",
    "бокалы": "бокал",
    "кофе зерно": "кофе",
    "салфетки": "салфетка",
    "одноразка": "одноразовая посуда",
}

app = FastAPI(title="Servio search-api", version=SERVICE_VERSION, docs_url="/docs", redoc_url="/redoc", openapi_url="/openapi.json")


def _opensearch_url() -> str:
    return os.getenv("OPENSEARCH_URL", "http://opensearch:9200").strip().rstrip("/")


def _index() -> str:
    return os.getenv("OPENSEARCH_PRODUCTS_INDEX", "products").strip()


def _timeout() -> float:
    return float(os.getenv("OPENSEARCH_TIMEOUT_SECONDS", "0.8"))


def _normalize(query: str) -> str:
    return " ".join((query or "").strip().lower().split())


def _rewrite(query: str) -> str:
    rewritten = _normalize(query)
    for source, target in SEMANTIC_QUERY_REWRITES.items():
        if source in rewritten:
            rewritten = rewritten.replace(source, target).strip()
    return rewritten


def _corrections(query: str, limit: int) -> list[str]:
    normalized = _normalize(query)
    result: list[str] = []
    alias = SEARCH_SYNONYMS.get(normalized)
    rewritten = _rewrite(normalized)
    for candidate in (alias, rewritten):
        if candidate and candidate != normalized and candidate not in result:
            result.append(candidate)
    return result[:limit]


def _payload(query: str, limit: int, country_limit: int) -> dict[str, object]:
    normalized = _normalize(query)
    rewritten = _rewrite(query)
    effective = rewritten or normalized
    return {
        "size": max(1, limit),
        "query": {
            "bool": {
                "should": [
                    {"multi_match": {"query": effective, "fields": ["name^6", "sku^5", "manufacturer_sku^4", "barcode^4", "brand^4", "series^3", "store_name^4", "seller_username^3", "category^3", "country_of_origin^3", "tags^2", "material^2", "purpose^2", "flavor^2", "description^2", "store_description^2"], "type": "most_fields", "operator": "or", "fuzziness": "AUTO"}},
                    {"prefix": {"name": {"value": effective, "boost": 9}}},
                    {"prefix": {"brand": {"value": effective, "boost": 6}}},
                    {"prefix": {"category": {"value": effective, "boost": 6}}},
                    {"term": {"sku.keyword": {"value": query, "boost": 12}}},
                    {"term": {"manufacturer_sku.keyword": {"value": query, "boost": 10}}},
                    {"term": {"barcode.keyword": {"value": query, "boost": 10}}},
                ],
                "minimum_should_match": 1,
            }
        },
        "suggest": {"query_suggest": {"prefix": effective, "completion": {"field": "suggest", "size": max(6, min(10, limit)), "skip_duplicates": True}}},
        "aggs": {"country_suggestions_scope": {"filter": {"prefix": {"country_of_origin_keyword": effective}}, "aggs": {"country_suggestions": {"terms": {"field": "country_of_origin.keyword", "size": max(1, country_limit), "order": {"_count": "desc"}}}}}},
    }


def _search(query: str, limit: int, country_limit: int) -> dict[str, object]:
    normalized = _normalize(query)
    rewritten = _rewrite(query)
    if not normalized:
        return {"product_ids": [], "suggestions": [], "countries": [], "effective_query": "", "rewritten_query": "", "rewrite_kind": ""}
    try:
        with httpx.Client(timeout=_timeout()) as client:
            response = client.post(f"{_opensearch_url()}/{_index()}/_search", json=_payload(query, limit, country_limit))
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"opensearch unavailable: {type(exc).__name__}") from exc
    ids: list[int] = []
    for hit in data.get("hits", {}).get("hits", []):
        source = hit.get("_source") or {}
        raw_id = source.get("id", hit.get("_id"))
        try:
            ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    suggestions: list[str] = []
    seen: set[str] = set()
    for entry in data.get("suggest", {}).get("query_suggest", []):
        for option in entry.get("options", []):
            text = " ".join(str(option.get("text") or "").split())
            key = text.casefold()
            if text and key not in seen:
                seen.add(key)
                suggestions.append(text)
    buckets = data.get("aggregations", {}).get("country_suggestions_scope", {}).get("country_suggestions", {}).get("buckets", [])
    countries = [str(item.get("key")) for item in buckets if item.get("key")][:country_limit]
    return {
        "product_ids": ids[:limit],
        "suggestions": suggestions,
        "countries": countries,
        "effective_query": rewritten or normalized,
        "rewritten_query": rewritten if rewritten != normalized else "",
        "rewrite_kind": "semantic_rewrite" if rewritten != normalized else "",
    }


@app.get("/health")
def health() -> dict[str, object]:
    return {"ok": True, "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.get("/ready")
def ready() -> dict[str, object]:
    try:
        with httpx.Client(timeout=max(1.0, _timeout())) as client:
            response = client.get(_opensearch_url())
            response.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"opensearch unavailable: {type(exc).__name__}") from exc
    return {"ok": True, "service": SERVICE_NAME}


@app.get("/v1/search/query")
def search_query(q: str = Query(default="", max_length=200), limit: int = Query(default=24, ge=1, le=64), country_limit: int = Query(default=6, ge=0, le=24), request_id: str = Query(default="", max_length=128), user_id: int = Query(default=0, ge=0)) -> dict[str, object]:
    bundle = _search(q, limit, country_limit)
    return {"ok": True, "query": q, "provider": "opensearch", **bundle, "corrections": _corrections(q, min(6, limit)), "facets": {}, "source": "opensearch", "request_id": request_id, "user_id": user_id}


@app.get("/v1/search/suggestions")
def search_suggestions(q: str = Query(default="", max_length=200), limit: int = Query(default=10, ge=1, le=32), country_limit: int = Query(default=6, ge=0, le=24), request_id: str = Query(default="", max_length=128), user_id: int = Query(default=0, ge=0)) -> dict[str, object]:
    bundle = _search(q, limit, country_limit)
    return {"ok": True, "query": q, "provider": "opensearch", "effective_query": bundle["effective_query"], "rewritten_query": bundle["rewritten_query"], "rewrite_kind": bundle["rewrite_kind"], "suggestions": bundle["suggestions"][:limit], "corrections": _corrections(q, min(6, limit)), "countries": bundle["countries"], "source": "opensearch", "request_id": request_id, "user_id": user_id}
