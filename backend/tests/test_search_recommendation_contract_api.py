import json

import pytest
from django.contrib.auth import get_user_model

from catalog.models import Brand, Category, Product

pytestmark = pytest.mark.django_db


def _make_product(*, sku: str, name: str, seller=None) -> Product:
    brand = Brand.objects.create(name=f"Brand-{sku}")
    category = Category.objects.create(name=f"Category-{sku}")
    return Product.objects.create(
        sku=sku,
        name=name,
        brand=brand,
        category=category,
        seller=seller,
        price="120.00",
        stock_qty=12,
        is_new=True,
    )


def test_search_query_contract_returns_products_and_facets(client, settings):
    settings.OPENSEARCH_ENABLED = False
    _make_product(sku="93000001", name="Сироп ванильный")

    response = client.get("/api/search/query/?q=сироп&limit=6")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["query"] == "сироп"
    assert payload["source"] in {"django-inline", "django-inline-fallback"}
    assert isinstance(payload["products"], list)
    assert payload["products"][0]["name"] == "Сироп ванильный"
    assert "facets" in payload
    assert "availability" in payload["facets"]


def test_search_query_contract_falls_back_when_fastapi_unavailable(client, settings, monkeypatch):
    settings.SEARCH_SERVICE_MODE = "fastapi"
    settings.OPENSEARCH_ENABLED = False
    _make_product(sku="93000002", name="Сироп карамельный")

    from shopfront.searching import contracts as search_contracts

    monkeypatch.setattr(search_contracts, "_remote_query_contract", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    response = client.get("/api/search/query/?q=сироп&limit=6")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["source"] == "django-inline-fallback"
    assert "service_error" in payload


def test_search_suggestions_contract_returns_payload(client, settings):
    settings.OPENSEARCH_ENABLED = False
    _make_product(sku="93000003", name="Кофе зерновой")

    response = client.get("/api/search/suggestions/?q=кофе&limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["query"] == "кофе"
    assert isinstance(payload["suggestions"], list)


def test_recommendation_home_contract_endpoint(client):
    response = client.get("/api/recommendations/home/?limit=6")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["recommendation_id"]
    assert payload["surface"] == "home"
    assert isinstance(payload["latency_ms"], int)
    assert payload["engine_source"] == "django-inline"
    assert payload["service_source"] == "django-inline"
    assert "fallback_source" in payload
    assert "empty_reason" in payload
    assert isinstance(payload["sections"], list)
    assert payload["sections"][0]["impression_id"]
    assert "fallback_source" in payload["sections"][0]
    assert "empty_reason" in payload["sections"][0]


def test_recommendation_product_and_cart_contract_endpoints(client):
    seller = get_user_model().objects.create_user(username="rec_seller", password="pass")
    seed = _make_product(sku="93000004", name="Кофе эспрессо", seller=seller)
    _make_product(sku="93000005", name="Кофе бленд", seller=seller)

    product_response = client.get(f"/api/recommendations/products/{seed.id}/?limit=6")
    cart_response = client.post(
        "/api/recommendations/cart/",
        data=json.dumps({"product_ids": [seed.id], "limit": 4}),
        content_type="application/json",
    )

    assert product_response.status_code == 200
    assert cart_response.status_code == 200
    product_payload = product_response.json()
    cart_payload = cart_response.json()
    assert product_payload["ok"] is True
    assert product_payload["surface"] == "pdp"
    assert product_payload["recommendation_id"]
    assert product_payload["engine_source"] == "django-inline"
    assert product_payload["service_source"] == "django-inline"
    assert cart_payload["ok"] is True
    assert cart_payload["surface"] == "cart"
    assert cart_payload["recommendation_id"]
    assert cart_payload["engine_source"] == "django-inline"
    assert cart_payload["service_source"] == "django-inline"
    assert cart_payload["sections"][0]["key"] == "cross_sell"


def test_recommendation_reorder_requires_auth(client):
    response = client.get("/api/recommendations/reorder/")

    assert response.status_code == 401
