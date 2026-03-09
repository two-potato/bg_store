import pytest

from catalog.models import Brand, Category, Product
from shopfront import search as sf_search
from shopfront.search_service import HybridSearchProvider, rewrite_query


pytestmark = pytest.mark.django_db


def test_rewrite_query_expands_marketplace_language():
    assert rewrite_query("одноразка для кофе") == "одноразовая посуда для кофе"


def test_hybrid_search_merges_lexical_and_semantic_candidates(settings, monkeypatch):
    settings.SEARCH_RERANK_ENABLED = True
    brand = Brand.objects.create(name="Hybrid Brand")
    category = Category.objects.create(name="Сиропы")
    lexical = Product.objects.create(sku="88000001", name="Ванильный сироп", brand=brand, category=category, price=10, stock_qty=2)
    semantic = Product.objects.create(sku="88000002", name="Сироп для бара", brand=brand, category=category, price=12, stock_qty=2)

    monkeypatch.setattr(sf_search, "live_search_bundle", lambda query, limit, country_limit: ([lexical.id], [], ["ванильный сироп"]))

    bundle = HybridSearchProvider().live_bundle("барный сироп", limit=5, country_limit=0)

    assert bundle.provider == "hybrid"
    assert lexical.id in bundle.product_ids
    assert semantic.id in bundle.product_ids
    assert bundle.rewritten_query == "сироп для бара"
    assert "сироп для бара" in bundle.suggestions


def test_hybrid_search_falls_back_when_es_unavailable(monkeypatch):
    brand = Brand.objects.create(name="Fallback Brand")
    category = Category.objects.create(name="Упаковка")
    product = Product.objects.create(
        sku="88000003",
        name="Takeaway упаковка",
        brand=brand,
        category=category,
        price=15,
        stock_qty=3,
        purpose="упаковка на вынос",
    )

    def _boom(*args, **kwargs):
        raise sf_search.ESSearchUnavailable("es down")

    monkeypatch.setattr(sf_search, "live_search_bundle", _boom)

    bundle = HybridSearchProvider().live_bundle("упаковка на вынос", limit=5, country_limit=0)

    assert bundle.product_ids[0] == product.id
    assert bundle.provider == "hybrid"
