import json
from types import SimpleNamespace

import pytest

from shopfront.recommendation import contracts as recommendation_contracts
from shopfront.searching import contracts as search_contracts


def _request(*, authenticated=True):
    user = SimpleNamespace(id=17, is_authenticated=authenticated)
    return SimpleNamespace(
        headers={"X-Request-ID": "req-17"},
        META={"HTTP_X_REQUEST_ID": "meta-req"},
        user=user,
    )


def _recommendation_payload(surface="home", *, products=False):
    section_products = [{"id": 1, "name": "Card"}] if products else []
    return {
        "ok": True,
        "surface": surface,
        "variant": "control",
        "source": "ranker-v1",
        "sections": [
            {
                "key": "main",
                "title": "Main",
                "source": "test",
                "strategy": "ranked",
                "products": section_products,
                "tracking_payload": json.dumps(
                    {
                        "event": "recommendation_impression",
                        "ecommerce": {"items": [{"item_id": "1"}]},
                    }
                ),
            }
        ],
    }


def test_recommendation_tracking_and_finalize_metadata():
    payload = _recommendation_payload(products=True)

    finalized = recommendation_contracts._finalize_payload(payload, latency_ms=23, fallback_source="remote_error")

    assert finalized["recommendation_id"]
    assert finalized["latency_ms"] == 23
    assert finalized["engine_source"] == "ranker-v1"
    assert finalized["service_source"] == "ranker-v1"
    assert finalized["fallback_source"] == "remote_error"
    assert finalized["empty_reason"] == ""
    section = finalized["sections"][0]
    assert section["impression_id"]
    assert section["fallback_source"] == "remote_error"
    tracking = json.loads(section["tracking_payload"])
    assert tracking["recommendation_id"] == finalized["recommendation_id"]
    assert tracking["impression_id"] == section["impression_id"]
    assert tracking["ecommerce"]["items"][0]["recommendation_id"] == finalized["recommendation_id"]


def test_recommendation_finalize_empty_and_error_reasons():
    empty = recommendation_contracts._finalize_payload(
        {"ok": True, "surface": "home", "sections": [{"key": "x", "products": []}]},
        latency_ms=1,
    )
    auth = recommendation_contracts._finalize_payload(
        {"ok": False, "error": "authentication_required", "sections": []},
        latency_ms=2,
    )
    missing = recommendation_contracts._finalize_payload(
        {"ok": False, "error": "product_not_found", "sections": []},
        latency_ms=3,
    )

    assert empty["empty_reason"] == "all_sections_empty"
    assert empty["sections"][0]["empty_reason"] == "no_products"
    assert auth["empty_reason"] == "authentication_required"
    assert missing["empty_reason"] == "product_not_found"
    assert recommendation_contracts._decorate_tracking_payload("not-json", recommendation_id="r", impression_id="i", fallback_source="", empty_reason="", engine_source="e", service_source="s", latency_ms=1) == "not-json"
    assert recommendation_contracts._decorate_tracking_payload("[]", recommendation_id="r", impression_id="i", fallback_source="", empty_reason="", engine_source="e", service_source="s", latency_ms=1) == "[]"
    assert recommendation_contracts._decorate_tracking_payload("", recommendation_id="r", impression_id="i", fallback_source="", empty_reason="", engine_source="e", service_source="s", latency_ms=1) == ""


def test_recommendation_remote_response_normalization(monkeypatch):
    monkeypatch.setattr(recommendation_contracts, "normalize_product_card", lambda item: {"id": int(item["id"]), "normalized": True})
    normalized = recommendation_contracts._normalize_remote_response(
        {
            "ok": True,
            "surface": "pdp",
            "variant": "ranked",
            "recommendation_id": "rec",
            "fallback_source": "",
            "empty_reason": "",
            "latency_ms": 7,
            "service_source": "recommendation-api",
            "engine_source": "ranker",
            "sections": [
                "bad",
                {
                    "key": "similar",
                    "title": "Similar",
                    "source": "remote",
                    "strategy": "ranked",
                    "tracking_payload": "{}",
                    "impression_id": "imp",
                    "products": [{"id": "5"}, "bad"],
                },
            ],
        }
    )

    assert normalized["ok"] is True
    assert normalized["surface"] == "pdp"
    assert normalized["sections"][0]["products"] == [{"id": 5, "normalized": True}]
    assert normalized["sections"][0]["impression_id"] == "imp"


def test_recommendation_request_metadata_helpers():
    request = _request()
    assert recommendation_contracts._request_id(request) == "req-17"
    assert recommendation_contracts._request_id(None) == ""
    params = recommendation_contracts._remote_params(request, limit=6)
    assert params == {"limit": 6, "request_id": "req-17", "user_id": 17}


def test_recommendation_home_fastapi_and_fallback(monkeypatch):
    request = _request()
    monkeypatch.setattr(recommendation_contracts, "_remote_call", lambda *args, **kwargs: _recommendation_payload("home"))
    fast = recommendation_contracts.recommendation_home_contract(request=request, mode_override="fastapi")
    assert fast["source"] == "fastapi"
    assert fast["service_source"] == "recommendation-api"

    monkeypatch.setattr(recommendation_contracts, "_remote_call", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(recommendation_contracts, "_local_home", lambda **kwargs: _recommendation_payload("home"))
    fallback = recommendation_contracts.recommendation_home_contract(request=request, mode_override="fastapi")
    assert fallback["source"] == "django-inline-fallback"
    assert fallback["fallback_source"] == "remote_error"
    assert fallback["service_error"] == "down"


def test_recommendation_product_modes(monkeypatch):
    request = _request()
    monkeypatch.setattr(recommendation_contracts, "_remote_call", lambda *args, **kwargs: _recommendation_payload("pdp"))
    fast = recommendation_contracts.recommendation_product_contract(request=request, product_id=9, mode_override="fastapi")
    assert fast["source"] == "fastapi"

    monkeypatch.setattr(recommendation_contracts, "_local_product", lambda **kwargs: _recommendation_payload("pdp"))
    inline = recommendation_contracts.recommendation_product_contract(request=request, product_id=9, mode_override="django-inline")
    assert inline["source"] == "django-inline"
    assert inline["engine_source"] == "django-inline"


def test_recommendation_product_section_fallback(monkeypatch):
    request = _request()
    monkeypatch.setattr(recommendation_contracts, "_remote_call", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("section-down")))
    monkeypatch.setattr(recommendation_contracts, "_local_product_section", lambda **kwargs: _recommendation_payload("pdp"))

    payload = recommendation_contracts.recommendation_product_section_contract(
        request=request,
        product_id=3,
        section="fbt",
        mode_override="fastapi",
    )

    assert payload["source"] == "django-inline-fallback"
    assert payload["service_error"] == "section-down"


def test_recommendation_cart_fastapi_and_inline(monkeypatch):
    request = _request()
    calls = []

    def remote(path, **kwargs):
        calls.append((path, kwargs))
        return _recommendation_payload("checkout")

    monkeypatch.setattr(recommendation_contracts, "_remote_call", remote)
    fast = recommendation_contracts.recommendation_cart_contract(
        request=request,
        product_ids=[1, 2],
        checkout=True,
        mode_override="fastapi",
    )
    assert fast["source"] == "fastapi"
    assert calls[0][0] == "/v1/recommendations/checkout"
    assert calls[0][1]["method"] == "POST"
    assert calls[0][1]["json_data"]["product_ids"] == [1, 2]

    monkeypatch.setattr(recommendation_contracts, "_local_cart_like", lambda **kwargs: _recommendation_payload("cart"))
    inline = recommendation_contracts.recommendation_cart_contract(
        request=request,
        product_ids=[1],
        checkout=False,
        mode_override="django-inline",
    )
    assert inline["source"] == "django-inline"


def test_recommendation_reorder_and_search_recovery_fallbacks(monkeypatch):
    request = _request()
    monkeypatch.setattr(recommendation_contracts, "_remote_call", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("remote-down")))
    monkeypatch.setattr(recommendation_contracts, "_local_reorder", lambda **kwargs: _recommendation_payload("reorder"))
    monkeypatch.setattr(recommendation_contracts, "_local_search_recovery", lambda **kwargs: _recommendation_payload("catalog"))

    reorder = recommendation_contracts.recommendation_reorder_contract(request=request, mode_override="fastapi")
    recovery = recommendation_contracts.recommendation_search_recovery_contract(
        request=request,
        query="coffee",
        mode_override="fastapi",
    )

    assert reorder["source"] == "django-inline-fallback"
    assert reorder["fallback_source"] == "remote_error"
    assert recovery["source"] == "django-inline-fallback"
    assert recovery["service_error"] == "remote-down"


def test_search_request_helpers_and_modes(monkeypatch):
    request = _request()
    assert search_contracts._request_id(request) == "req-17"
    assert search_contracts._request_id(None) == ""
    assert search_contracts._user_id(request) == 17
    assert search_contracts._user_id(_request(authenticated=False)) == 0
    assert search_contracts._user_id(None) == 0

    monkeypatch.setattr(
        search_contracts,
        "_remote_query_contract",
        lambda **kwargs: {"ok": True, "source": "opensearch", "product_ids": [1], "products": []},
    )
    fast = search_contracts.search_query_contract(query="coffee", request=request, mode_override="fastapi")
    assert fast["source"] == "fastapi"
    assert fast["engine_source"] == "opensearch"
    assert fast["service_source"] == "search-api"

    monkeypatch.setattr(search_contracts, "_remote_query_contract", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("search-down")))
    monkeypatch.setattr(search_contracts, "_local_query_contract", lambda **kwargs: {"ok": True, "products": [], "product_ids": []})
    fallback = search_contracts.search_query_contract(query="coffee", request=request, mode_override="fastapi")
    assert fallback["source"] == "django-inline-fallback"
    assert fallback["service_error"] == "search-down"

    inline = search_contracts.search_query_contract(query="coffee", request=request, mode_override="django-inline")
    assert inline["source"] == "django-inline"
    assert inline["engine_source"] == "django-inline"


def test_search_suggestions_fastapi_fallback_and_inline(monkeypatch):
    request = _request()
    monkeypatch.setattr(
        search_contracts,
        "_remote_suggestions_contract",
        lambda **kwargs: {"ok": True, "source": "suggest-v1", "suggestions": ["coffee"]},
    )
    fast = search_contracts.search_suggestions_contract(query="cof", request=request, mode_override="fastapi")
    assert fast["source"] == "fastapi"
    assert fast["engine_source"] == "suggest-v1"

    monkeypatch.setattr(search_contracts, "_remote_suggestions_contract", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("suggest-down")))
    monkeypatch.setattr(search_contracts, "_local_suggestions_contract", lambda **kwargs: {"ok": True, "suggestions": ["coffee"]})
    fallback = search_contracts.search_suggestions_contract(query="cof", request=request, mode_override="fastapi")
    assert fallback["source"] == "django-inline-fallback"
    assert fallback["service_error"] == "suggest-down"

    inline = search_contracts.search_suggestions_contract(query="cof", request=request, mode_override="django-inline")
    assert inline["source"] == "django-inline"


def test_search_facets_cover_counts_prices_and_invalid_price():
    brand = SimpleNamespace(id=1, name="Brand")
    category = SimpleNamespace(id=2, name="Category")
    products = [
        SimpleNamespace(brand=brand, category=category, display_stock_qty=3, stock_qty=3, display_price="10.50", price="10.50"),
        SimpleNamespace(brand=brand, category=category, display_stock_qty=0, stock_qty=0, display_price="bad", price="bad"),
    ]

    facets = search_contracts._search_facets(products)

    assert facets["brands"] == [{"id": 1, "label": "Brand", "count": 2}]
    assert facets["categories"] == [{"id": 2, "label": "Category", "count": 2}]
    assert facets["availability"] == {"in_stock": 1, "out_of_stock": 1}
    assert facets["price"] == {"min": "10.50", "max": "10.50"}
