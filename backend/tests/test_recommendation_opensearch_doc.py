import pytest
from django.contrib.auth import get_user_model

from catalog.models import Brand, Category, Collection, Product, ProductDocument, Tag
from catalog.opensearch_index import product_doc


pytestmark = pytest.mark.django_db


def test_product_doc_contains_recommendation_fields():
    seller = get_user_model().objects.create_user(username="seller_os_doc", password="pass")
    brand = Brand.objects.create(name="Brand Doc")
    category = Category.objects.create(name="Category Doc")
    tag = Tag.objects.create(name="vanilla")
    product = Product.objects.create(
        seller=seller,
        brand=brand,
        category=category,
        sku="33330001",
        name="Vanilla Syrup",
        price="2400.00",
        stock_qty=12,
        min_order_qty=2,
        lead_time_days=1,
        pack_qty=6,
    )
    product.tags.add(tag)
    collection = Collection.objects.create(name="Bar Essentials")
    collection.products.add(product)
    ProductDocument.objects.create(product=product, title="Certificate", kind=ProductDocument.Kind.CERTIFICATE, file_url="https://example.com/cert.pdf")

    doc = product_doc(product)

    assert doc["brand_id"] == brand.id
    assert doc["category_id"] == category.id
    assert doc["seller_id"] == seller.id
    assert doc["stock_qty"] == 12
    assert doc["min_order_qty"] == 2
    assert doc["lead_time_days"] == 1
    assert doc["has_fast_delivery"] is True
    assert doc["pack_qty"] == 6
    assert doc["price_bucket"] == "mid"
    assert doc["seller_is_verified"] is False
    assert "procurement_fit_score" in doc
    assert collection.id in doc["collection_ids"]
    assert tag.id in doc["tag_ids"]
    assert doc["has_documents"] is True
    assert doc["has_certificate"] is True
