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
    ProductReviewPhoto,
    ProductQuestion,
    Series,
    Tag,
)
from commerce.models import DeliveryAddress, LegalEntity, LegalEntityMembership, SellerStore
from orders.models import Order, OrderItem, SellerOrder, SellerOrderItem
from users.models import UserProfile
from users.views_html import _company_workspace_rows
from shopfront.search_service import SearchBundle


pytestmark = pytest.mark.django_db


def _query_count(client, url: str, **headers) -> int:
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(url, **headers)
    assert resp.status_code == 200
    return len(ctx.captured_queries)


def _post_query_count(client, url: str, data, **headers) -> int:
    with CaptureQueriesContext(connection) as ctx:
        resp = client.post(url, data=data, content_type="application/json", **headers)
    assert resp.status_code == 201
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


def test_order_api_create_query_growth_is_sublinear(api_client, user):
    brand, category, series, _ = _catalog_entities()
    products = _make_products(
        brand,
        category,
        series,
        Tag.objects.create(name="N1TagCreateApi", slug="n1-tag-create-api"),
        amount=3,
        offset=360,
    )

    le = LegalEntity.objects.create(
        name="N1 Create LE",
        inn="7707083898",
        bik="044525225",
        checking_account="40702810900000000008",
    )
    LegalEntityMembership.objects.create(user=user, legal_entity=le)
    addr = DeliveryAddress.objects.create(
        legal_entity=le, label="Office", country="RU", city="Msk", street="Lenina", postcode="101000"
    )

    small = _post_query_count(
        api_client,
        "/api/orders/",
        {
            "legal_entity_id": le.id,
            "delivery_address_id": addr.id,
            "items": [{"product_id": product.id, "qty": 2} for product in products[:2]],
        },
    )

    products.extend(
        _make_products(
            brand,
            category,
            series,
            Tag.objects.create(name="N1TagCreateApiMore", slug="n1-tag-create-api-more"),
            amount=8,
            offset=380,
        )
    )
    large = _post_query_count(
        api_client,
        "/api/orders/",
        {
            "legal_entity_id": le.id,
            "delivery_address_id": addr.id,
            "items": [{"product_id": product.id, "qty": 2} for product in products],
        },
    )

    assert large <= small + 8


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


def test_product_detail_query_growth_with_photos_and_questions_is_sublinear(client):
    brand, category, series, _ = _catalog_entities()
    product = Product.objects.create(
        sku="20000002",
        name="N1 Detail Product Rich",
        brand=brand,
        category=category,
        series=series,
        price=109,
        stock_qty=10,
    )
    ProductImage.objects.create(product=product, url="https://example.com/detail-rich.jpg", ordering=0)

    reviewers = [get_user_model().objects.create_user(username=f"n1rich{i}", password="pass") for i in range(2)]
    for idx, reviewer in enumerate(reviewers):
        review = ProductReview.objects.create(product=product, user=reviewer, rating=5, text=f"review {idx}")
        ProductReviewComment.objects.create(review=review, user=reviewer, text=f"comment {idx}")
        ProductReviewPhoto.objects.create(review=review, image_url=f"https://example.com/review-{idx}.jpg", ordering=idx)
        ProductQuestion.objects.create(product=product, user=reviewer, question_text=f"question {idx}", is_public=True)

    small = _query_count(client, f"/product/{product.slug}/")

    more_reviewers = [get_user_model().objects.create_user(username=f"n1richx{i}", password="pass") for i in range(8)]
    for idx, reviewer in enumerate(more_reviewers):
        review = ProductReview.objects.create(product=product, user=reviewer, rating=4, text=f"extra review {idx}")
        ProductReviewComment.objects.create(review=review, user=reviewer, text=f"extra comment {idx}")
        ProductReviewPhoto.objects.create(review=review, image_url=f"https://example.com/review-extra-{idx}.jpg", ordering=idx)
        ProductQuestion.objects.create(product=product, user=reviewer, question_text=f"extra question {idx}", is_public=True)

    large = _query_count(client, f"/product/{product.slug}/")

    assert large <= small + 5


def test_account_orders_query_growth_is_sublinear(client_logged, user):
    brand, category, series, tag = _catalog_entities()
    products = _make_products(brand, category, series, tag, amount=4, offset=500)
    le = LegalEntity.objects.create(
        name="Account LE",
        inn="7707083894",
        bik="044525225",
        checking_account="40702810900000000002",
    )
    LegalEntityMembership.objects.create(user=user, legal_entity=le)
    addr = DeliveryAddress.objects.create(
        legal_entity=le, label="HQ", country="RU", city="Msk", street="Tverskaya", postcode="101001"
    )
    for i in range(2):
        order = Order.objects.create(legal_entity=le, placed_by=user, delivery_address=addr)
        for product in products[:2]:
            OrderItem.objects.create(order=order, product=product, name=f"{product.name}-{i}", price=product.price, qty=1)

    small = _query_count(client_logged, "/account/orders/")

    for i in range(8):
        order = Order.objects.create(legal_entity=le, placed_by=user, delivery_address=addr)
        for product in products:
            OrderItem.objects.create(order=order, product=product, name=f"{product.name}-x{i}", price=product.price, qty=2)

    large = _query_count(client_logged, "/account/orders/")

    assert large <= small + 5


def test_company_workspace_rows_do_not_query_per_membership(user):
    entities = []
    for i in range(3):
        le = LegalEntity.objects.create(
            name=f"Workspace LE {i}",
            inn=f"77070838{i}5",
            bik="044525225",
            checking_account=f"4070281090000000001{i}",
        )
        LegalEntityMembership.objects.create(user=user, legal_entity=le)
        entities.append(le)

    memberships = LegalEntityMembership.objects.select_related("legal_entity").filter(user=user)

    with CaptureQueriesContext(connection) as ctx:
        rows = _company_workspace_rows(user, memberships)

    assert len(rows) == 3
    assert len(ctx.captured_queries) <= 12


def test_account_comments_query_growth_is_sublinear(client_logged, user):
    brand, category, series, _ = _catalog_entities()
    product = Product.objects.create(
        sku="50000001",
        name="Commented product",
        brand=brand,
        category=category,
        series=series,
        price=110,
        stock_qty=7,
    )
    ProductImage.objects.create(product=product, url="https://example.com/commented.jpg", ordering=0)

    for i in range(2):
        review_author = get_user_model().objects.create_user(username=f"base-commenter{i}", password="pass")
        review = ProductReview.objects.create(product=product, user=review_author, rating=5, text=f"review {i}")
        ProductReviewComment.objects.create(review=review, user=user, text=f"comment {i}")

    small = _query_count(client_logged, "/account/comments/")

    for i in range(10):
        other = get_user_model().objects.create_user(username=f"commenter{i}", password="pass")
        review = ProductReview.objects.create(product=product, user=other, rating=4, text=f"extra review {i}")
        ProductReviewComment.objects.create(review=review, user=user, text=f"extra comment {i}")

    large = _query_count(client_logged, "/account/comments/")

    assert large <= small + 4


def test_account_seller_home_query_growth_is_sublinear(client_logged, user):
    profile = UserProfile.objects.get(user=user)
    profile.role = UserProfile.Role.SELLER
    profile.save(update_fields=["role"])

    le = LegalEntity.objects.create(
        name="Seller N1 LE",
        inn="7707083896",
        bik="044525225",
        checking_account="40702810900000000016",
    )
    LegalEntityMembership.objects.create(user=user, legal_entity=le)
    store = SellerStore.objects.create(owner=user, legal_entity=le, name="Seller N1 Store")

    brand, category, series, tag = _catalog_entities()
    products = _make_products(brand, category, series, tag, amount=4, offset=700)
    for product in products:
        product.seller = user
        product.save(update_fields=["seller"])

    base_order = Order.objects.create(legal_entity=le, placed_by=user)
    seller_order = SellerOrder.objects.create(order=base_order, seller=user, seller_store_name=store.name)
    for product in products[:2]:
        order_item = OrderItem.objects.create(order=base_order, product=product, name=product.name, price=product.price, qty=1)
        SellerOrderItem.objects.create(
            seller_order=seller_order,
            order_item=order_item,
            product=product,
            name=product.name,
            price=product.price,
            qty=1,
        )

    small = _query_count(client_logged, "/account/seller/")

    for i in range(7):
        order = Order.objects.create(legal_entity=le, placed_by=user)
        seller_order = SellerOrder.objects.create(order=order, seller=user, seller_store_name=store.name)
        for product in products:
            order_item = OrderItem.objects.create(order=order, product=product, name=f"{product.name}-{i}", price=product.price, qty=2)
            SellerOrderItem.objects.create(
                seller_order=seller_order,
                order_item=order_item,
                product=product,
                name=f"{product.name}-{i}",
                price=product.price,
                qty=2,
            )

    large = _query_count(client_logged, "/account/seller/")

    assert large <= small + 4


def test_live_search_query_growth_is_sublinear(client, monkeypatch):
    brand, category, series, tag = _catalog_entities()
    products = _make_products(brand, category, series, tag, amount=3, offset=900)

    class _Provider:
        def live_bundle(self, query, limit, country_limit):
            return SearchBundle(
                product_ids=[product.id for product in products],
                countries=[],
                suggestions=[],
                provider="test",
            )

    monkeypatch.setattr("shopfront.views.get_search_provider", lambda: _Provider())
    small = _query_count(client, "/search/live/?q=N1%20Prod", HTTP_HX_REQUEST="true")

    products.extend(_make_products(brand, category, series, tag, amount=12, offset=950))
    large = _query_count(client, "/search/live/?q=N1%20Prod", HTTP_HX_REQUEST="true")

    assert large <= small + 3


def test_cart_panel_query_growth_is_sublinear(client):
    brand, category, series, tag = _catalog_entities()
    products = _make_products(brand, category, series, tag, amount=2, offset=1000)
    session = client.session
    session["cart"] = {str(product.id): {"qty": 1} for product in products}
    session.save()
    small = _query_count(client, "/cart/panel/")

    products.extend(_make_products(brand, category, series, tag, amount=8, offset=1020))
    session = client.session
    session["cart"] = {str(product.id): {"qty": 1} for product in products}
    session.save()
    large = _query_count(client, "/cart/panel/")

    assert large <= small + 3
