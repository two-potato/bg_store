from __future__ import annotations

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from catalog.models import Brand, Category, Product
from shopfront.recommendation.contracts import recommendation_home_contract, recommendation_reorder_contract
from shopfront.searching.contracts import search_query_contract

pytestmark = pytest.mark.django_db


def _make_product(*, sku: str, name: str) -> Product:
    brand = Brand.objects.create(name=f"Brand-{sku}")
    category = Category.objects.create(name=f"Category-{sku}")
    return Product.objects.create(
        sku=sku,
        name=name,
        brand=brand,
        category=category,
        price="90.00",
        stock_qty=5,
    )


def _anon_request(path: str = "/"):
    request = RequestFactory().get(path)
    request.user = AnonymousUser()
    return request


def test_search_fastapi_mode_adds_engine_and_service_markers(settings, monkeypatch):
    settings.SEARCH_SERVICE_MODE = "fastapi"
    remote_payload = {
        "ok": True,
        "source": "django-inline",
        "query": "syrup",
        "effective_query": "syrup",
        "rewritten_query": "",
        "rewrite_kind": "",
        "provider": "hybrid",
        "product_ids": [],
        "products": [],
        "suggestions": [],
        "corrections": [],
        "countries": [],
        "facets": {
            "brands": [],
            "categories": [],
            "availability": {"in_stock": 0, "out_of_stock": 0},
            "price": {"min": "0.00", "max": "0.00"},
        },
    }
    monkeypatch.setattr("shopfront.searching.contracts._remote_query_contract", lambda **kwargs: remote_payload)

    payload = search_query_contract(query="syrup", limit=3, country_limit=0, request=_anon_request("/api/search/query/"))

    assert payload["source"] == "fastapi"
    assert payload["service_source"] == "search-api"
    assert payload["engine_source"] == "django-inline"


def test_recommendation_fastapi_mode_adds_engine_and_service_markers(settings, monkeypatch):
    settings.RECOMMENDATION_SERVICE_MODE = "fastapi"
    remote_payload = {
        "ok": True,
        "source": "django-inline",
        "surface": "home",
        "variant": "control",
        "sections": [],
    }
    monkeypatch.setattr("shopfront.recommendation.contracts._remote_call", lambda *args, **kwargs: remote_payload)

    payload = recommendation_home_contract(request=_anon_request("/api/recommendations/home/"), limit=3)

    assert payload["source"] == "fastapi"
    assert payload["service_source"] == "recommendation-api"
    assert payload["engine_source"] == "django-inline"


def test_recommendation_reorder_supports_user_id_override(user):
    payload = recommendation_reorder_contract(
        request=_anon_request("/api/recommendations/reorder/"),
        limit=4,
        mode_override="django-inline",
        user_id_override=user.id,
    )

    assert payload["ok"] is True
    assert payload["source"] == "django-inline"
    assert payload["engine_source"] == "django-inline"
    assert payload["sections"][0]["key"] == "reorder"


def test_internal_contract_endpoints_require_token_and_serve_inline_contract(client, settings):
    settings.OPENSEARCH_ENABLED = False
    _make_product(sku="94000001", name="Сироп лайм")

    forbidden = client.get("/api/internal/search/query/?q=сироп&limit=2")
    allowed = client.get(
        "/api/internal/search/query/?q=сироп&limit=2",
        HTTP_X_INTERNAL_TOKEN=settings.INTERNAL_TOKEN,
    )

    assert forbidden.status_code == 403
    assert allowed.status_code == 200
    payload = allowed.json()
    assert payload["source"] == "django-inline"
    assert payload["engine_source"] == "django-inline"

