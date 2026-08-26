import pytest
from catalog.models import Brand, Category, Collection, Product, Series

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
    # Collections
    collection = Collection.objects.create(name="Launch Kit", is_active=True)
    collection.products.add(Product.objects.first())
    r3b = client.get("/api/catalog/collections/")
    assert r3b.status_code == 200 and r3b.json()
    # Products + filters
    r4 = client.get("/api/catalog/products/?brand=%d&category=%d" % (b.id, c.id))
    assert r4.status_code == 200 and r4.json()


def test_catalog_products_support_search_collection_and_category_path_filters(client):
    brand = Brand.objects.create(name="Complaex Signature")
    category_root = Category.objects.create(name="Посуда")
    category_child = Category.objects.create(name="Тарелки", parent=category_root)
    series = Series.objects.create(brand=brand, name="Night Shift")

    product_root = Product.objects.create(
        sku="10000001",
        name="Набор сервировки Root",
        brand=brand,
        series=series,
        category=category_root,
        price=10,
        stock_qty=5,
    )
    product_child = Product.objects.create(
        sku="10000002",
        name="Тарелка Night Shift 21 см",
        brand=brand,
        series=series,
        category=category_child,
        manufacturer_sku="NIGHT-21",
        price=12,
        stock_qty=8,
    )

    collection = Collection.objects.create(name="Bar Launch", is_active=True)
    collection.products.add(product_child)

    search_response = client.get("/api/catalog/products/?q=Night+Shift")
    assert search_response.status_code == 200
    assert any(item["id"] == product_child.id for item in search_response.json())

    collection_response = client.get(f"/api/catalog/products/?collection_slug={collection.slug}")
    assert collection_response.status_code == 200
    assert [item["id"] for item in collection_response.json()] == [product_child.id]

    category_response = client.get(
        f"/api/catalog/products/?category_path={category_root.full_slug_path}&include_descendants=true"
    )
    assert category_response.status_code == 200
    ids = [item["id"] for item in category_response.json()]
    assert product_root.id in ids
    assert product_child.id in ids
