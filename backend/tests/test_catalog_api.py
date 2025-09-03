import pytest
from catalog.models import Brand, Category, Product, Series

pytestmark = pytest.mark.django_db


def test_catalog_list_endpoints(client, db):
    b = Brand.objects.create(name="BrandA")
    s = Series.objects.create(brand=b, name="S1")
    c = Category.objects.create(name="Cat")
    Product.objects.create(sku="SKU1", name="P1", brand=b, series=s, category=c, price=10, stock_qty=5)

    # Brands
    r1 = client.get("/api/catalog/brands/")
    assert r1.status_code == 200 and r1.json()
    # Series
    r2 = client.get("/api/catalog/series/")
    assert r2.status_code == 200 and r2.json()
    # Categories
    r3 = client.get("/api/catalog/categories/")
    assert r3.status_code == 200 and r3.json()
    # Products + filters
    r4 = client.get("/api/catalog/products/?brand=%d&category=%d" % (b.id, c.id))
    assert r4.status_code == 200 and r4.json()
