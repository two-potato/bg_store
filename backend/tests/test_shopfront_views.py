import pytest
from django.contrib.auth import get_user_model
from catalog.models import Brand, Category, Country, Product, ProductReview, ProductReviewComment, Series, Tag
from shopfront import search as sf_search
from commerce.models import LegalEntity, LegalEntityMembership, DeliveryAddress, SellerStore
from orders.models import Order, FakeAcquiringPayment
from shopfront.tasks import notify_contact_feedback
from users.models import UserProfile

pytestmark = pytest.mark.django_db


def _prod():
    b = Brand.objects.create(name="B")
    s = Series.objects.create(brand=b, name="S")
    c = Category.objects.create(name="C")
    p = Product.objects.create(sku="SKU-X", name="PX", brand=b, series=s, category=c, price=15, stock_qty=100)
    t = Tag.objects.create(name="Good", slug="good")
    p.tags.add(t)
    return p, b, c, t


def test_home_and_catalog_pages(client, db):
    p, b, c, t = _prod()
    # home
    r1 = client.get("/")
    assert r1.status_code == 200
    # catalog with filters
    r2 = client.get(f"/catalog/?brand={b.id}&category={c.slug}&q=P&tag={t.slug}")
    assert r2.status_code == 200


def test_home_with_malformed_cart_entries(client, db):
    p, *_ = _prod()
    s = client.session
    s["cart"] = {
        "bad-id": {"qty": "oops"},
        str(p.id): {"qty": 1},
    }
    s.save()
    r = client.get("/")
    assert r.status_code == 200


def test_product_page(client, db):
    p, *_ = _prod()
    r = client.get(f"/product/{p.slug}/")
    assert r.status_code == 200


def test_product_page_contains_store_link(client, db):
    p, *_ = _prod()
    User = get_user_model()
    seller = User.objects.create_user(username="seller_page", password="pass")
    prof = UserProfile.objects.get(user=seller)
    prof.role = UserProfile.Role.SELLER
    prof.save(update_fields=["role"])
    le = LegalEntity.objects.create(name="LE Seller Page", inn="7707083893", bik="044525225", checking_account="40702810900000001001")
    store = SellerStore.objects.create(owner=seller, legal_entity=le, name="Store Page")
    p.seller = seller
    p.save(update_fields=["seller"])

    r = client.get(f"/product/{p.slug}/")
    assert r.status_code == 200
    assert f"/stores/{store.slug}/" in r.text


def test_store_and_seller_profile_pages(client, db):
    p, *_ = _prod()
    User = get_user_model()
    seller = User.objects.create_user(username="seller_profile_page", password="pass")
    prof = UserProfile.objects.get(user=seller)
    prof.role = UserProfile.Role.SELLER
    prof.full_name = "Продавец Тестовый"
    prof.save(update_fields=["role", "full_name"])
    le = LegalEntity.objects.create(name="LE Seller Profile", inn="7715964180", bik="044525225", checking_account="40702810900000001002")
    LegalEntityMembership.objects.create(user=seller, legal_entity=le)
    store = SellerStore.objects.create(owner=seller, legal_entity=le, name="Store Seller Profile", description="Store description")
    p.seller = seller
    p.save(update_fields=["seller"])

    r_store = client.get(f"/stores/{store.slug}/")
    assert r_store.status_code == 200
    assert "Store description" in r_store.text
    assert p.name in r_store.text
    assert f"/sellers/{seller.profile.slug}/" in r_store.text

    r_seller = client.get(f"/sellers/{seller.profile.slug}/")
    assert r_seller.status_code == 200
    assert le.name in r_seller.text
    assert store.name in r_seller.text


def test_product_legacy_pk_redirects_to_slug(client, db):
    p, *_ = _prod()
    r = client.get(f"/product/{p.id}/")
    assert r.status_code in (301, 302)
    assert r.headers.get("Location", "").endswith(f"/product/{p.slug}/")


def test_store_and_seller_legacy_redirects_to_slug(client, db):
    User = get_user_model()
    seller = User.objects.create_user(username="legacy_slug_seller", password="pass")
    le = LegalEntity.objects.create(name="Legacy LE", inn="7707083894", bik="044525225", checking_account="40702810900000001003")
    store = SellerStore.objects.create(owner=seller, legal_entity=le, name="Legacy Store")

    r_store_legacy = client.get(f"/stores/{store.id}/")
    assert r_store_legacy.status_code in (301, 302)
    assert r_store_legacy.headers.get("Location", "").endswith(f"/stores/{store.slug}/")

    r_seller_legacy = client.get(f"/sellers/{seller.username}/")
    assert r_seller_legacy.status_code in (301, 302)
    assert r_seller_legacy.headers.get("Location", "").endswith(f"/sellers/{seller.profile.slug}/")

def test_live_search_htmx_from_three_symbols(client, monkeypatch, db):
    b = Brand.objects.create(name="LiveBrand")
    c = Category.objects.create(name="LiveCategory")
    p1 = Product.objects.create(
        sku="12345678",
        name="Memory Syrup Pro",
        brand=b,
        category=c,
        price=99,
        stock_qty=3,
    )
    p2 = Product.objects.create(
        sku="87654321",
        name="Coffee Beans",
        brand=b,
        category=c,
        price=49,
        stock_qty=3,
    )
    monkeypatch.setattr(sf_search, "live_search_bundle", lambda query, limit, country_limit: ([p1.id, p2.id], []))

    short_resp = client.get("/search/live/?q=me", HTTP_HX_REQUEST="true")
    assert short_resp.status_code == 200
    assert short_resp.text.strip() == ""

    live_resp = client.get("/search/live/?q=mem", HTTP_HX_REQUEST="true")
    assert live_resp.status_code == 200
    assert "Memory Syrup Pro" in live_resp.text
    assert "live-search-panel" in live_resp.text
    assert "live-search-head__label" in live_resp.text
    assert "live-search-head__query" in live_resp.text
    assert "live-search-thumb" in live_resp.text
    assert "/product/" in live_resp.text


def test_live_search_matches_store_name(client, monkeypatch, db):
    b = Brand.objects.create(name="StoreBrand")
    c = Category.objects.create(name="StoreCategory")
    p = Product.objects.create(
        sku="22334455",
        name="Store linked product",
        brand=b,
        category=c,
        price=10,
        stock_qty=2,
    )
    User = get_user_model()
    seller = User.objects.create_user(username="store_search_seller", password="pass")
    prof = UserProfile.objects.get(user=seller)
    prof.role = UserProfile.Role.SELLER
    prof.save(update_fields=["role"])
    le = LegalEntity.objects.create(name="Store Search LE", inn="500100012001", bik="044525225", checking_account="40702810900000002001")
    SellerStore.objects.create(owner=seller, legal_entity=le, name="Aurora Storehouse")
    p.seller = seller
    p.save(update_fields=["seller"])

    monkeypatch.setattr(sf_search, "live_search_bundle", lambda query, limit, country_limit: ([], []))
    r = client.get("/search/live/?q=Aurora", HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    assert "Store linked product" in r.text


def test_live_search_country_popular_suggestions(client, monkeypatch, db):
    country = Country.objects.create(name="Аргентина", iso_code="ARG")
    b = Brand.objects.create(name="CountryBrand")
    c = Category.objects.create(name="CountryCategory")
    Product.objects.create(
        sku="55667788",
        name="Country product",
        brand=b,
        category=c,
        country_of_origin=country,
        price=11,
        stock_qty=1,
    )
    monkeypatch.setattr(sf_search, "live_search_bundle", lambda query, limit, country_limit: ([], ["Аргентина"]))
    r = client.get("/search/live/?q=арг", HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    assert "Популярные страны" in r.text
    assert "Аргентина" in r.text


def test_live_search_partial_uses_fallback_image_when_product_has_no_images(client, monkeypatch, db):
    b = Brand.objects.create(name="NoImgBrand")
    c = Category.objects.create(name="NoImgCategory")
    p = Product.objects.create(
        sku="11223344",
        name="No image product",
        brand=b,
        category=c,
        price=10,
        stock_qty=1,
    )
    monkeypatch.setattr(sf_search, "live_search_bundle", lambda query, limit, country_limit: ([p.id], []))
    r = client.get("/search/live/?q=noi", HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    assert f"https://picsum.photos/seed/live-{p.id}/96/96" in r.text

def test_live_search_uses_es_results_when_available(client, monkeypatch, db):
    b = Brand.objects.create(name="ESBrand")
    c = Category.objects.create(name="ESCategory")
    p1 = Product.objects.create(sku="10000001", name="AAA", brand=b, category=c, price=1, stock_qty=1)
    p2 = Product.objects.create(sku="10000002", name="BBB", brand=b, category=c, price=2, stock_qty=1)

    monkeypatch.setattr(sf_search, "live_search_bundle", lambda query, limit, country_limit: ([p2.id, p1.id], []))
    r = client.get("/search/live/?q=bbb", HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    assert r.text.find("BBB") < r.text.find("AAA")


def test_catalog_q_uses_es_ids_only(client, monkeypatch, db):
    b = Brand.objects.create(name="CatESBrand")
    c = Category.objects.create(name="CatESCategory")
    Product.objects.create(sku="10010001", name="Alpha", brand=b, category=c, price=1, stock_qty=1)
    p2 = Product.objects.create(sku="10010002", name="Beta", brand=b, category=c, price=2, stock_qty=1)

    monkeypatch.setattr("shopfront.views.search_product_ids", lambda query, limit: [p2.id])
    r = client.get("/catalog/?q=alpha")
    assert r.status_code == 200
    assert "Beta" in r.text
    assert "Alpha" not in r.text


def test_catalog_sort_by_rating_desc(client, db):
    b = Brand.objects.create(name="RatingBrand")
    c = Category.objects.create(name="RatingCategory")
    low = Product.objects.create(sku="10020001", name="LowRate", brand=b, category=c, price=1, stock_qty=1)
    high = Product.objects.create(sku="10020002", name="HighRate", brand=b, category=c, price=1, stock_qty=1)
    User = get_user_model()
    u1 = User.objects.create_user(username="r1", password="pass")
    u2 = User.objects.create_user(username="r2", password="pass")
    ProductReview.objects.create(product=low, user=u1, rating=2, text="ok")
    ProductReview.objects.create(product=high, user=u1, rating=5, text="great")
    ProductReview.objects.create(product=high, user=u2, rating=4, text="good")

    r = client.get("/catalog/?sort=rating_desc")
    assert r.status_code == 200
    assert r.text.find("HighRate") < r.text.find("LowRate")


def test_catalog_category_reset_link_preserves_sort_and_brand(client, db):
    b = Brand.objects.create(name="B1")
    c = Category.objects.create(name="ReviewCategory")
    Product.objects.create(sku="11112222", name="P1", brand=b, category=c, price=10, stock_qty=2)
    r = client.get(f"/catalog/?category={c.slug}&brand={b.id}&sort=price_desc")
    assert r.status_code == 200
    assert "Сбросить категорию" in r.text
    assert f'href="/catalog/?brand={b.id}&amp;sort=price_desc"' in r.text


def test_catalog_invalid_page_falls_back_to_first_page(client, db):
    _prod()
    r = client.get("/catalog/?page=not-a-number")
    assert r.status_code == 200


def test_catalog_invalid_brand_does_not_error(client, db):
    _prod()
    r = client.get("/catalog/?brand=oops")
    assert r.status_code == 200


def test_live_search_es_unavailable_returns_empty(client, monkeypatch, db):
    from catalog.models import Country
    country = Country.objects.create(name="Italy", iso_code="IT")
    b = Brand.objects.create(name="Lavazza")
    c = Category.objects.create(name="Кофе")
    Product.objects.create(
        sku="20000001",
        name="Coffee Gold",
        brand=b,
        category=c,
        country_of_origin=country,
        price=123,
        stock_qty=4,
    )

    def _boom(*args, **kwargs):
        raise sf_search.ESSearchUnavailable("es down")

    monkeypatch.setattr(sf_search, "live_search_bundle", _boom)

    r_country = client.get("/search/live/?q=italy", HTTP_HX_REQUEST="true")
    assert r_country.status_code == 200
    assert "Coffee Gold" not in r_country.text

    r_category = client.get("/search/live/?q=кофе", HTTP_HX_REQUEST="true")
    assert r_category.status_code == 200
    assert "Coffee Gold" not in r_category.text

    r_brand = client.get("/search/live/?q=lavazza", HTTP_HX_REQUEST="true")
    assert r_brand.status_code == 200
    assert "Coffee Gold" not in r_brand.text


def test_static_info_pages(client, db):
    assert client.get("/about/").status_code == 200
    assert client.get("/delivery/").status_code == 200
    assert client.get("/contacts/").status_code == 200


def test_contacts_feedback_submits_and_schedules_notify(client, monkeypatch, db):
    sent = {}

    def _fake_delay(**kwargs):
        sent.update(kwargs)
        return None

    monkeypatch.setattr(notify_contact_feedback, "delay", _fake_delay)
    r = client.post(
        "/contacts/",
        {"name": "Ivan", "phone": "+79001234567", "message": "Нужна консультация по заказу"},
        follow=True,
    )
    assert r.status_code == 200
    assert sent["name"] == "Ivan"
    assert sent["phone"] == "+79001234567"
    assert "консультация" in sent["message"]
    assert sent["source"].endswith("/contacts/")


def test_cart_flow(client, db):
    p, *_ = _prod()
    # badge/panel empty
    r_badge0 = client.get("/cart/badge/")
    assert r_badge0.status_code == 200
    assert "0" in r_badge0.text
    assert client.get("/cart/panel/").status_code == 200
    # add
    r_add = client.post("/cart/add/", {"product_id": p.id, "qty": 2})
    assert r_add.status_code == 200
    assert 'id="cart-badge"' in r_add.text
    assert 'hx-swap-oob="outerHTML"' in r_add.text
    assert "cartChanged" in (r_add.headers.get("HX-Trigger") or "")
    r_badge1 = client.get("/cart/badge/")
    assert "2" in r_badge1.text
    assert "30" in r_badge1.text
    # update inc
    r_u1 = client.post("/cart/update/", {"product_id": p.id, "op": "inc"})
    assert r_u1.status_code == 200
    assert 'hx-swap-oob="outerHTML"' in r_u1.text
    r_badge2 = client.get("/cart/badge/")
    assert "3" in r_badge2.text
    assert "45" in r_badge2.text
    # update set
    r_u2 = client.post("/cart/update/", {"product_id": p.id, "op": "set", "qty": 5})
    assert r_u2.status_code == 200
    assert 'hx-swap-oob="outerHTML"' in r_u2.text
    r_badge3 = client.get("/cart/badge/")
    assert "5" in r_badge3.text
    assert "75" in r_badge3.text
    # remove
    r_rm = client.post("/cart/remove/", {"product_id": str(p.id)})
    assert r_rm.status_code == 200
    assert 'hx-swap-oob="outerHTML"' in r_rm.text
    r_badge4 = client.get("/cart/badge/")
    assert "0" in r_badge4.text
    # update for non-existing item -> 404 branch
    r_u3 = client.post("/cart/update/", {"product_id": p.id, "op": "inc"})
    assert r_u3.status_code == 404
    # clear
    r_cl = client.post("/cart/clear/")
    assert r_cl.status_code == 200
    assert 'hx-swap-oob="outerHTML"' in r_cl.text


def test_checkout_company_and_individual(client_logged, user, db):
    p, *_ = _prod()
    user.profile.discount = 10
    user.profile.save(update_fields=["discount"])
    # Prepare membership and address
    le = LegalEntity.objects.create(name="LE", inn="7707083893", bik="044525225", checking_account="40702810900000000001")
    LegalEntityMembership.objects.create(user=user, legal_entity=le)
    addr = DeliveryAddress.objects.create(legal_entity=le, label="Ofc", country="RU", city="Msk", street="Lenina", postcode="101000")
    # Put item to session cart
    s = client_logged.session
    s["cart"] = {str(p.id): {"qty": 1}}
    s.save()

    # checkout page
    r_page = client_logged.get("/checkout/")
    assert r_page.status_code == 200

    # company submit
    r_sub = client_logged.post("/checkout/submit/", {
        "customer_type": "company",
        "payment_method": "cash",
        "legal_entity": le.id,
        "delivery_address": addr.id,
    })
    # redirect to orders page
    assert r_sub.status_code in (302, 303)
    first = Order.objects.filter(placed_by=user).order_by("-id").first()
    assert str(first.subtotal) == "15.00"
    assert str(first.discount_amount) == "1.50"
    assert str(first.total) == "13.50"

    # individual submit
    s = client_logged.session
    s["cart"] = {str(p.id): {"qty": 2}}
    s.save()
    r_sub2 = client_logged.post("/checkout/submit/", {
        "customer_type": "individual",
        "payment_method": "cash",
        "customer_name": "Ivan",
        "customer_phone": "+71234567890",
        "address_text": "Street 1",
    })
    assert r_sub2.status_code in (302, 303)
    second = Order.objects.filter(placed_by=user).order_by("-id").first()
    assert str(second.subtotal) == "30.00"
    assert str(second.discount_amount) == "3.00"
    assert str(second.total) == "27.00"


def test_checkout_mir_card_creates_fake_payment_panel(client_logged, user, db):
    p, *_ = _prod()
    s = client_logged.session
    s["cart"] = {str(p.id): {"qty": 1}}
    s.save()

    r = client_logged.post(
        "/checkout/submit/",
        {
            "customer_type": "individual",
            "payment_method": "mir_card",
            "customer_name": "Ivan",
            "customer_phone": "+71234567890",
            "address_text": "Street 1",
        },
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    assert "Тестовый эквайринг" in r.text
    order = Order.objects.filter(placed_by=user).order_by("-id").first()
    assert order.payment_method == Order.PaymentMethod.MIR_CARD
    payment = FakeAcquiringPayment.objects.get(order=order)
    assert payment.status in (FakeAcquiringPayment.Status.CREATED, FakeAcquiringPayment.Status.PROCESSING)


def test_fake_payment_event_success_marks_order_paid(client_logged, user, db):
    p, *_ = _prod()
    order = Order.objects.create(
        customer_type=Order.CustomerType.INDIVIDUAL,
        payment_method=Order.PaymentMethod.MIR_CARD,
        customer_name="Ivan",
        customer_phone="+79999999999",
        address_text="Addr",
        placed_by=user,
    )
    Order.objects.filter(pk=order.pk).update(status=Order.Status.NEW)
    FakeAcquiringPayment.objects.create(
        order=order,
        amount=15,
        provider_payment_id=f"fake_{order.id}",
        status=FakeAcquiringPayment.Status.PROCESSING,
        last_event=FakeAcquiringPayment.Event.START,
        history=[],
    )

    r = client_logged.post(
        f"/payments/fake/{order.id}/event/",
        {"event": "success"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    assert "Оплачен" in r.text
    order.refresh_from_db()
    payment = FakeAcquiringPayment.objects.get(order=order)
    assert order.status == Order.Status.PAID
    assert payment.status == FakeAcquiringPayment.Status.PAID


def test_product_review_upsert_create_and_update(client_logged, user, db):
    p, *_ = _prod()

    r1 = client_logged.post(
        f"/product/{p.slug}/review/",
        {"rating": "5", "text": "Отличный товар"},
    )
    assert r1.status_code in (302, 303)
    assert ProductReview.objects.filter(product=p, user=user).count() == 1
    review = ProductReview.objects.get(product=p, user=user)
    assert review.rating == 5
    assert review.text == "Отличный товар"

    r2 = client_logged.post(
        f"/product/{p.slug}/review/",
        {"rating": "3", "text": "Нормально"},
    )
    assert r2.status_code in (302, 303)
    assert ProductReview.objects.filter(product=p, user=user).count() == 1
    review.refresh_from_db()
    assert review.rating == 3
    assert review.text == "Нормально"


def test_product_review_upsert_requires_auth(client, db):
    p, *_ = _prod()
    r = client.post(f"/product/{p.slug}/review/", {"rating": "4", "text": "ok"})
    assert r.status_code in (302, 303)
    assert "/account/login/" in r.headers.get("Location", "")


def test_product_page_contains_reviews_block(client_logged, user, db):
    p, *_ = _prod()
    ProductReview.objects.create(product=p, user=user, rating=4, text="Good")
    r = client_logged.get(f"/product/{p.slug}/")
    assert r.status_code == 200
    assert 'id="product-reviews"' in r.text
    assert "Отзывы и рейтинг" in r.text
    assert "Good" in r.text


def test_product_review_upsert_htmx_returns_updated_reviews_panel(client_logged, user, db):
    p, *_ = _prod()
    r = client_logged.post(
        f"/product/{p.slug}/review/",
        {"rating": "5", "text": "new htmx text"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    assert 'id="product-reviews"' in r.text
    assert "new htmx text" in r.text
    assert "5" in r.text
    assert "<textarea" in r.text
    assert ProductReview.objects.filter(product=p, user=user).count() == 1
    assert ProductReview.objects.get(product=p, user=user).rating == 5


def test_product_review_delete_by_author_htmx(client_logged, user, db):
    p, *_ = _prod()
    ProductReview.objects.create(product=p, user=user, rating=4, text="to delete")
    r = client_logged.post(
        f"/product/{p.slug}/review/delete/",
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    assert ProductReview.objects.filter(product=p, user=user).count() == 0
    assert 'id="product-reviews"' in r.text


def test_product_review_comment_create_update_delete_htmx(client_logged, user, db):
    p, *_ = _prod()
    review = ProductReview.objects.create(product=p, user=user, rating=5, text="base")

    r_create = client_logged.post(
        f"/product/{p.slug}/review/{review.id}/comment/",
        {"text": "first comment"},
        HTTP_HX_REQUEST="true",
    )
    assert r_create.status_code == 200
    comment = ProductReviewComment.objects.get(review=review, user=user)
    assert comment.text == "first comment"

    r_update = client_logged.post(
        f"/product/{p.slug}/comment/{comment.id}/update/",
        {"text": "updated comment"},
        HTTP_HX_REQUEST="true",
    )
    assert r_update.status_code == 200
    comment.refresh_from_db()
    assert comment.text == "updated comment"

    r_delete = client_logged.post(
        f"/product/{p.slug}/comment/{comment.id}/delete/",
        HTTP_HX_REQUEST="true",
    )
    assert r_delete.status_code == 200
    assert ProductReviewComment.objects.filter(pk=comment.id).count() == 0


def test_rating_visible_in_product_card_on_home(client_logged, user, db):
    p, *_ = _prod()
    ProductReview.objects.create(product=p, user=user, rating=4, text="ok")

    r = client_logged.get("/")
    assert r.status_code == 200
    assert "★" in r.text
    assert "4.0" in r.text
