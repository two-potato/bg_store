import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext

from catalog.models import (
    Brand,
    Category,
    Product,
    ProductImage,
    ProductReview,
    ProductReviewComment,
    Series,
    Tag,
)
from commerce.models import DeliveryAddress, LegalEntity, LegalEntityMembership
from orders.models import Order, OrderItem


pytestmark = pytest.mark.django_db


def _query_count(client, url: str, **headers) -> int:
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(url, **headers)
    assert resp.status_code == 200
    return len(ctx.captured_queries)


def _catalog_entities():
    brand = Brand.objects.create(name="N1Brand")
    category = Category.objects.create(name="N1Category")
    series = Series.objects.create(brand=brand, name="N1Series")
    tag = Tag.objects.create(name="N1Tag", slug="n1-tag")
    return brand, category, series, tag


def _make_products(brand, category, series, tag, amount: int, offset: int = 0):
    created = []
    for i in range(offset, offset + amount):
        p = Product.objects.create(
            sku=f"{10000000 + i}",
            name=f"N1 Product {i}",
            brand=brand,
            category=category,
            series=series,
            price=100 + i,
            stock_qty=20,
        )
        p.tags.add(tag)
        ProductImage.objects.create(product=p, url=f"https://example.com/{i}.jpg", ordering=0)
        created.append(p)
    return created


def test_catalog_page_query_growth_is_sublinear(client):
    brand, category, series, tag = _catalog_entities()
    _make_products(brand, category, series, tag, amount=3, offset=0)
    small = _query_count(client, "/catalog/")

    _make_products(brand, category, series, tag, amount=18, offset=100)
    large = _query_count(client, "/catalog/")

    assert large <= small + 4


def test_order_api_list_query_growth_is_sublinear(api_client, user):
    brand, category, series, _ = _catalog_entities()
    products = _make_products(
        brand,
        category,
        series,
        Tag.objects.create(name="N1TagApi", slug="n1-tag-api"),
        amount=4,
        offset=300,
    )

    le = LegalEntity.objects.create(
        name="N1 LE",
        inn="7707083893",
        bik="044525225",
        checking_account="40702810900000000001",
    )
    LegalEntityMembership.objects.create(user=user, legal_entity=le)
    addr = DeliveryAddress.objects.create(
        legal_entity=le, label="Office", country="RU", city="Msk", street="Lenina", postcode="101000"
    )

    for _ in range(2):
        order = Order.objects.create(legal_entity=le, placed_by=user, delivery_address=addr)
        for p in products[:2]:
            OrderItem.objects.create(order=order, product=p, name=p.name, price=p.price, qty=1)

    small = _query_count(api_client, "/api/orders/")

    for i in range(8):
        order = Order.objects.create(legal_entity=le, placed_by=user, delivery_address=addr)
        for p in products:
            OrderItem.objects.create(order=order, product=p, name=f"{p.name}-{i}", price=p.price, qty=2)

    large = _query_count(api_client, "/api/orders/")

    assert large <= small + 5


def test_product_detail_query_growth_is_sublinear(client):
    brand, category, series, _ = _catalog_entities()
    product = Product.objects.create(
        sku="20000001",
        name="N1 Detail Product",
        brand=brand,
        category=category,
        series=series,
        price=99,
        stock_qty=8,
    )
    ProductImage.objects.create(product=product, url="https://example.com/detail.jpg", ordering=0)

    User = get_user_model()
    base_users = [User.objects.create_user(username=f"n1u{i}", password="pass") for i in range(3)]
    for idx, u in enumerate(base_users):
        review = ProductReview.objects.create(product=product, user=u, rating=5 - idx, text=f"review {idx}")
        ProductReviewComment.objects.create(review=review, user=u, text=f"comment {idx}")

    small = _query_count(client, f"/product/{product.slug}/")

    extra_users = [User.objects.create_user(username=f"n1x{i}", password="pass") for i in range(8)]
    for idx, u in enumerate(extra_users):
        review = ProductReview.objects.create(product=product, user=u, rating=4, text=f"extra review {idx}")
        ProductReviewComment.objects.create(review=review, user=u, text=f"extra comment {idx}")

    large = _query_count(client, f"/product/{product.slug}/")

    assert large <= small + 5
