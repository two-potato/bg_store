import pytest
from django.contrib.auth import get_user_model
from catalog.models import Brand, Category, Collection, CollectionItem, Country, Product, ProductDocument, ProductQuestion, ProductReview, ProductReviewComment, ProductReviewPhoto, ProductReviewVote, Series, Tag, SellerOffer, SellerInventory
from shopfront import search as sf_search
from shopfront.search_service import SearchBundle
from commerce.models import LegalEntity, LegalEntityMembership, DeliveryAddress, SellerStore, StoreReview
from orders.models import Order, FakeAcquiringPayment
from promotions.models import Coupon, PromotionRule, PromotionRedemption
from shopfront.models import SavedList
from shopfront.tasks import notify_contact_feedback
from users.models import UserProfile
from catalog.models import ProductImage

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


def test_base_layout_uses_modular_frontend_assets(client, db):
    _prod()
    response = client.get("/")
    assert response.status_code == 200
    assert "shopfront/css/legacy/foundation.css" in response.text
    assert "shopfront/css/legacy/catalog-mobile.css" in response.text
    assert "shopfront/css/legacy/marketplace-surfaces.css" in response.text
    assert "shopfront/css/legacy/footer-and-grid.css" in response.text
    assert "shopfront/css/legacy/entity-pages-and-header.css" in response.text
    assert "shopfront/css/legacy/catalog-compact-and-grid.css" in response.text
    assert "shopfront/css/tokens.css" in response.text
    assert "shopfront/css/base.css" in response.text
    assert "shopfront/css/layout.css" in response.text
    assert "shopfront/css/components/header.css" in response.text
    assert "shopfront/css/components/brands.css" in response.text
    assert "shopfront/css/components/footer.css" in response.text
    assert "shopfront/css/components/product.css" in response.text
    assert "shopfront/css/components/live-search.css" in response.text
    assert "shopfront/css/components/account.css" in response.text
    assert "shopfront/css/components/toast.css" in response.text
    assert "shopfront/ui.runtime.js" in response.text
    assert "shopfront/ui.product-cards.js" in response.text
    assert "shopfront/ui.interactions.js" in response.text
    assert "shopfront/ui.social.js" in response.text
    assert "shopfront/unified-theme.css" not in response.text
    assert "shopfront/servio.css" not in response.text
    assert "shopfront/theme.css" not in response.text
    assert "shopfront/refactor.frontend.css" not in response.text
    assert "shopfront/ui.carousel.js" not in response.text
    assert "hyperscript.org" not in response.text
    assert "html-to-design/capture.js" not in response.text
    assert 'data-compare-launcher' in response.text
    assert 'hidden aria-hidden="true"' in response.text
    assert 'site-catalog-menu' in response.text
    assert 'site-header-v3__more-menu' in response.text
    assert ">Каталог</span></summary>" in response.text
    assert 'href="#main-content"' in response.text
    assert 'id="main-content"' in response.text


def test_robots_and_sitemap_exclude_private_routes(client, db):
    p, *_ = _prod()
    collection = Collection.objects.create(name="SEO Collection", is_active=True)
    store_owner = get_user_model().objects.create_user(username="seo_store_owner", password="pass")
    le = LegalEntity.objects.create(name="SEO LE", inn="7707083899", bik="044525225", checking_account="40702810900000001009")
    SellerStore.objects.create(owner=store_owner, legal_entity=le, name="SEO Store")
    collection.products.add(p)

    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Disallow: /metrics" in robots.text
    assert "Disallow: /api/docs/" in robots.text
    assert "Disallow: /checkout/" in robots.text

    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert "/product/" in sitemap.text
    assert "/brands/" in sitemap.text
    assert "/collections/" in sitemap.text
    assert "/stores/" in sitemap.text
    assert "<lastmod>" in sitemap.text
    assert "/cart/" not in sitemap.text
    assert "/checkout/" not in sitemap.text


def test_product_cards_use_static_placeholder_and_clean_alt_text(client, db):
    p, *_ = _prod()
    ProductImage.objects.create(product=p, url="https://example.com/demo.jpg", alt="Load Product 123456")

    response = client.get("/")
    assert response.status_code == 200
    assert "shopfront/product-placeholder.svg" in response.text
    assert 'alt="PX"' in response.text


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
    assert "product_view" in r.text


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


def test_product_page_shows_commercial_fields_and_documents(client, db):
    p, *_ = _prod()
    p.min_order_qty = 6
    p.lead_time_days = 4
    p.manufacturer_sku = "MFG-7788"
    p.save(update_fields=["min_order_qty", "lead_time_days", "manufacturer_sku"])
    ProductDocument.objects.create(
        product=p,
        title="Сертификат соответствия",
        kind=ProductDocument.Kind.CERTIFICATE,
        file_url="https://example.com/cert.pdf",
    )

    r = client.get(f"/product/{p.slug}/")
    assert r.status_code == 200
    assert "Минимальный заказ" in r.text
    assert "от 6" in r.text
    assert "4 дн." in r.text
    assert "Документы и сертификаты" in r.text
    assert "Сертификат соответствия" in r.text
    assert "https://example.com/cert.pdf" in r.text


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
    reviewer = User.objects.create_user(username="seller_rating_reviewer", password="pass")
    ProductReview.objects.create(product=p, user=reviewer, rating=5, text="great seller")
    StoreReview.objects.create(store=store, user=reviewer, rating=5, text="great store")

    r_store = client.get(f"/stores/{store.slug}/")
    assert r_store.status_code == 200
    assert "Store description" in r_store.text
    assert p.name in r_store.text
    assert f"/sellers/{seller.profile.slug}/" in r_store.text
    assert "Рейтинг магазина 5.0 / 5" in r_store.text

    r_seller = client.get(f"/sellers/{seller.profile.slug}/")
    assert r_seller.status_code == 200
    assert le.name in r_seller.text
    assert store.name in r_seller.text
    assert "Рейтинг продавца 5.0 / 5" in r_seller.text


def test_store_review_can_be_created_from_store_page(client_logged, user, db):
    p, *_ = _prod()
    seller = get_user_model().objects.create_user(username="store_review_seller", password="pass")
    le = LegalEntity.objects.create(name="Store Review LE", inn="7715964181", bik="044525225", checking_account="40702810900000001022")
    LegalEntityMembership.objects.create(user=seller, legal_entity=le)
    store = SellerStore.objects.create(owner=seller, legal_entity=le, name="Store Review Store")
    p.seller = seller
    p.save(update_fields=["seller"])

    response = client_logged.post(f"/stores/{store.slug}/review/", {"rating": "5", "text": "Надёжный магазин"})

    assert response.status_code == 302
    review = StoreReview.objects.get(store=store, user=user)
    assert review.rating == 5
    assert review.text == "Надёжный магазин"


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
    assert r_seller_legacy.status_code in (200, 301, 302)
    if r_seller_legacy.status_code in (301, 302):
        assert r_seller_legacy.headers.get("Location", "").endswith(f"/sellers/{seller.profile.slug}/")


def test_brand_slug_redirect_and_collection_detail_pages(client, db):
    brand = Brand.objects.create(name="Collection Brand")
    category = Category.objects.create(name="Collection Category")
    product = Product.objects.create(sku="90000001", name="Collection product", brand=brand, category=category, price=10, stock_qty=2)
    collection = Collection.objects.create(name="Spring Launch", is_active=True, is_featured=True)
    CollectionItem.objects.create(collection=collection, product=product, ordering=1)

    legacy = client.get(f"/brands/{brand.id}/")
    assert legacy.status_code in (301, 302)
    assert legacy.headers["Location"].endswith(f"/brands/{brand.slug}/")

    detail = client.get(f"/brands/{brand.slug}/")
    assert detail.status_code == 200
    assert "Spring Launch" in detail.text
    assert "Brand showcase" in detail.text

    collection_page = client.get(f"/collections/{collection.slug}/")
    assert collection_page.status_code == 200
    assert "Collection product" in collection_page.text


def test_home_and_brands_use_generated_brand_logos_and_static_hero_images(client, db):
    brand = Brand.objects.create(name="Northline Table")
    category = Category.objects.create(name="Brand Visual Category")
    Product.objects.create(sku="90000012", name="Brand visual product", brand=brand, category=category, price=12, stock_qty=4)

    home = client.get("/")
    assert home.status_code == 200
    assert "shopfront/hero/servio-hero-main.svg" in home.text
    assert "data:image/svg+xml;charset=UTF-8" in home.text
    assert "servio-home__brand-card" in home.text

    brands = client.get("/brands/")
    assert brands.status_code == 200
    assert "brand-index-2026__card" in brands.text
    assert "data:image/svg+xml;charset=UTF-8" in brands.text


def test_category_detail_page_and_offer_price(client, db):
    brand = Brand.objects.create(name="Category Brand")
    category = Category.objects.create(name="Coffee Syrups", hero_title="Сиропы для бара", landing_body="SEO body for category")
    seller = get_user_model().objects.create_user(username="cat_offer_seller", password="pass")
    le = LegalEntity.objects.create(name="Category Offer LE", inn="500100012002", bik="044525225", checking_account="40702810900000002002")
    store = SellerStore.objects.create(owner=seller, legal_entity=le, name="Bar Store")
    product = Product.objects.create(sku="90000002", name="Vanilla Syrup", brand=brand, category=category, price=199, stock_qty=1, seller=seller)
    offer = SellerOffer.objects.create(product=product, seller=seller, seller_store=store, price=149, min_order_qty=2)
    SellerInventory.objects.create(offer=offer, warehouse_name="Main", stock_qty=9, reserved_qty=1, eta_days=1, is_primary=True)

    r = client.get(f"/catalog/categories/{category.slug}/")
    assert r.status_code == 200
    assert "Сиропы для бара" in r.text
    assert "SEO body for category" in r.text
    assert "149" in r.text

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


def test_live_search_shows_typo_recovery_suggestions(client, monkeypatch, db):
    monkeypatch.setattr(sf_search, "live_search_bundle", lambda query, limit, country_limit: ([], [], []))
    Brand.objects.create(name="Сироп")
    Category.objects.create(name="Посуда")

    r = client.get("/search/live/?q=сиропы", HTTP_HX_REQUEST="true")
    assert r.status_code == 200
    assert "Подсказки" in r.text
    assert "/catalog/?q=%D1%81%D0%B8%D1%80%D0%BE%D0%BF" in r.text
    assert "Перейти в каталог и посмотреть альтернативы" in r.text


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
    assert "/media/user_photos/image017.jpg" in r.text

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

    class _Provider:
        def live_bundle(self, query, limit, country_limit):
            return SearchBundle(product_ids=[p2.id], countries=[], suggestions=[], provider="test")

    monkeypatch.setattr("shopfront.views.get_search_provider", lambda: _Provider())
    r = client.get("/catalog/?q=alpha")
    assert r.status_code == 200
    assert "Beta" in r.text
    assert "Alpha" not in r.text


def test_catalog_parent_category_includes_descendants(client, db):
    b = Brand.objects.create(name="DescBrand")
    parent = Category.objects.create(name="Parent")
    child = Category.objects.create(name="Child", parent=parent)
    Product.objects.create(sku="10010003", name="Child product", brand=b, category=child, price=2, stock_qty=1)

    r = client.get(f"/catalog/?category={parent.slug}")
    assert r.status_code == 200
    assert "Child product" in r.text
    assert "Parent" in r.text


def test_catalog_supports_seller_filter_and_facets(client, db):
    b = Brand.objects.create(name="SellerFacetBrand")
    c = Category.objects.create(name="SellerFacetCategory")
    User = get_user_model()
    seller = User.objects.create_user(username="facet_seller", password="pass")
    le = LegalEntity.objects.create(name="Seller Facet LE", inn="7707083801", bik="044525225", checking_account="40702810900000003001")
    store = SellerStore.objects.create(owner=seller, legal_entity=le, name="Facet Store")
    Product.objects.create(sku="10030001", name="Seller product", brand=b, category=c, price=20, stock_qty=2, seller=seller)
    Product.objects.create(sku="10030002", name="Other product", brand=b, category=c, price=25, stock_qty=2)

    r = client.get(f"/catalog/?seller={store.slug}")
    assert r.status_code == 200
    assert "Seller product" in r.text
    assert "Other product" not in r.text
    assert "Facet Store" in r.text
    assert 'name="seller"' in r.text


def test_catalog_supports_delivery_eta_filter(client, db):
    b = Brand.objects.create(name="EtaBrand")
    c = Category.objects.create(name="EtaCategory")
    Product.objects.create(sku="10030011", name="Fast item", brand=b, category=c, price=20, stock_qty=2, lead_time_days=2)
    Product.objects.create(sku="10030012", name="Slow item", brand=b, category=c, price=25, stock_qty=2, lead_time_days=10)

    r = client.get("/catalog/?delivery_eta=fast")
    assert r.status_code == 200
    assert "Fast item" in r.text
    assert "Slow item" not in r.text
    assert "Поставка: до 2 дней" in r.text


def test_catalog_zero_results_shows_recovery_and_fallback_products(client, monkeypatch, db):
    b = Brand.objects.create(name="FallbackBrand")
    c = Category.objects.create(name="FallbackCategory")
    Product.objects.create(sku="10030003", name="Fallback item", brand=b, category=c, price=99, stock_qty=5, is_new=True)

    class _Provider:
        def live_bundle(self, query, limit, country_limit):
            return SearchBundle(product_ids=[], countries=[], suggestions=[], provider="test")

    monkeypatch.setattr("shopfront.views.get_search_provider", lambda: _Provider())
    r = client.get("/catalog/?q=сиропы")
    assert r.status_code == 200
    assert "Возможно, вы искали" in r.text
    assert "Fallback item" in r.text


def test_saved_lists_create_from_favorites_and_move_to_cart(client_logged, user, db):
    p, *_ = _prod()
    client_logged.post("/favorites/toggle/", {"product_id": p.id})

    r_create = client_logged.post("/lists/", {"action": "create_from_favorites"})
    assert r_create.status_code in (302, 303)
    saved_list = SavedList.objects.get(user=user)
    assert saved_list.items.count() == 1

    r_detail = client_logged.post(f"/lists/{saved_list.id}/", {"action": "move_to_cart"})
    assert r_detail.status_code in (302, 303)
    session_cart = client_logged.session.get("cart", {})
    assert str(p.id) in session_cart


def test_saved_list_can_be_created_from_order(client_logged, user, db):
    p, *_ = _prod()
    order = Order.objects.create(
        customer_type=Order.CustomerType.INDIVIDUAL,
        payment_method=Order.PaymentMethod.CASH,
        customer_name="Ivan",
        customer_phone="+79999999999",
        address_text="Addr",
        placed_by=user,
    )
    order.items.create(product=p, name=p.name, price=p.price, qty=3)

    r = client_logged.post(f"/lists/from-order/{order.id}/")
    assert r.status_code in (302, 303)
    saved_list = SavedList.objects.filter(user=user).order_by("-id").first()
    assert saved_list.source == SavedList.Source.ORDER
    assert saved_list.items.first().quantity == 3


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
    assert "Coffee Gold" in r_category.text

    r_brand = client.get("/search/live/?q=lavazza", HTTP_HX_REQUEST="true")
    assert r_brand.status_code == 200
    assert "Coffee Gold" in r_brand.text


def test_static_info_pages(client, db):
    assert client.get("/about/").status_code == 200
    assert client.get("/delivery/").status_code == 200
    assert client.get("/contacts/").status_code == 200


def test_recently_viewed_products_are_shown_on_product_page(client, db):
    b = Brand.objects.create(name="RecentBrand")
    c = Category.objects.create(name="RecentCategory")
    p1 = Product.objects.create(sku="33334444", name="First product", brand=b, category=c, price=10, stock_qty=1)
    p2 = Product.objects.create(sku="33334445", name="Second product", brand=b, category=c, price=10, stock_qty=1)

    assert client.get(f"/product/{p1.slug}/").status_code == 200
    r = client.get(f"/product/{p2.slug}/")
    assert r.status_code == 200
    assert "Вы недавно смотрели" in r.text
    assert "First product" in r.text


def test_favorite_toggle_returns_tracking_payload(client, user, db):
    p, *_ = _prod()
    client.force_login(user)

    r = client.post("/favorites/toggle/", {"product_id": p.id})
    assert r.status_code == 200
    payload = r.json()
    assert payload["ok"] is True
    assert payload["tracking"]["event"] == "wishlist_add"


def test_checkout_contains_begin_checkout_payload(client_logged, user, db):
    p, *_ = _prod()
    s = client_logged.session
    s["cart"] = {str(p.id): {"qty": 2}}
    s.save()

    r = client_logged.get("/checkout/")
    assert r.status_code == 200
    assert "begin_checkout" in r.text
    assert "checkout_step_view" in r.text
    assert 'name="_idem"' in r.text
    assert 'data-checkout-cart=' in r.text


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


def test_catalog_card_uses_actual_cart_qty_from_session(client, db):
    p, *_ = _prod()
    s = client.session
    s["cart"] = {str(p.id): {"qty": 4}}
    s.save()

    r = client.get(f"/catalog/?q={p.name}")
    assert r.status_code == 200
    assert 'data-pid="%s"' % p.id in r.text
    assert '>4</span>' in r.text


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


def test_checkout_applies_valid_coupon(client_logged, user, db):
    p, *_ = _prod()
    rule = PromotionRule.objects.create(
        name="WELCOME10",
        discount_type=PromotionRule.DiscountType.PERCENT,
        discount_value="10.00",
        customer_scope=PromotionRule.CustomerScope.ALL,
    )
    Coupon.objects.create(code="WELCOME10", rule=rule, is_active=True)
    s = client_logged.session
    s["cart"] = {str(p.id): {"qty": 2}}
    s.save()

    r = client_logged.post(
        "/checkout/submit/",
        {
            "customer_type": "individual",
            "payment_method": "cash",
            "customer_name": "Ivan",
            "customer_email": "ivan@example.com",
            "customer_phone": "+71234567890",
            "address_text": "Street 1",
            "coupon_code": "WELCOME10",
        },
    )

    assert r.status_code in (302, 303)
    order = Order.objects.filter(placed_by=user).order_by("-id").first()
    assert order.coupon_code == "WELCOME10"
    assert str(order.discount_amount) == "3.00"
    assert str(order.total) == "27.00"
    redemption = PromotionRedemption.objects.get(order=order)
    assert redemption.coupon.code == "WELCOME10"
    assert str(redemption.discount_amount) == "3.00"


def test_checkout_rejects_invalid_coupon(client_logged, user, db):
    p, *_ = _prod()
    s = client_logged.session
    s["cart"] = {str(p.id): {"qty": 1}}
    s.save()

    r = client_logged.post(
        "/checkout/submit/",
        {
            "customer_type": "individual",
            "payment_method": "cash",
            "customer_name": "Ivan",
            "customer_email": "ivan@example.com",
            "customer_phone": "+71234567890",
            "address_text": "Street 1",
            "coupon_code": "NOTFOUND",
        },
        HTTP_HX_REQUEST="true",
    )

    assert r.status_code == 422
    assert "Промокод не найден" in r.text


def test_coupon_does_not_reduce_existing_profile_discount(client_logged, user, db):
    p, *_ = _prod()
    user.profile.discount = 20
    user.profile.save(update_fields=["discount"])
    rule = PromotionRule.objects.create(
        name="SMALL5",
        discount_type=PromotionRule.DiscountType.PERCENT,
        discount_value="5.00",
        customer_scope=PromotionRule.CustomerScope.ALL,
    )
    Coupon.objects.create(code="SMALL5", rule=rule, is_active=True)
    s = client_logged.session
    s["cart"] = {str(p.id): {"qty": 2}}
    s.save()

    r = client_logged.post(
        "/checkout/submit/",
        {
            "customer_type": "individual",
            "payment_method": "cash",
            "customer_name": "Ivan",
            "customer_email": "ivan@example.com",
            "customer_phone": "+71234567890",
            "address_text": "Street 1",
            "coupon_code": "SMALL5",
        },
    )

    assert r.status_code in (302, 303)
    order = Order.objects.filter(placed_by=user).order_by("-id").first()
    assert str(order.discount_amount) == "6.00"
    assert str(order.total) == "24.00"


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


def test_guest_checkout_page_is_available(client, db):
    p, *_ = _prod()
    s = client.session
    s["cart"] = {str(p.id): {"qty": 1}}
    s.save()

    r = client.get("/checkout/")

    assert r.status_code == 200
    assert "Гостевой checkout доступен" in r.text
    assert 'name="customer_email"' in r.text


def test_guest_checkout_individual_creates_public_order(client, db):
    p, *_ = _prod()
    s = client.session
    s["cart"] = {str(p.id): {"qty": 2}}
    s.save()

    r = client.post(
        "/checkout/submit/",
        {
            "customer_type": "individual",
            "payment_method": "cash",
            "customer_name": "Guest Buyer",
            "customer_email": "guest@example.com",
            "customer_phone": "+79990000000",
            "address_text": "Guest street 1",
        },
        HTTP_HX_REQUEST="true",
    )

    assert r.status_code == 200
    order = Order.objects.order_by("-id").first()
    assert order.placed_by is None
    assert order.customer_email == "guest@example.com"
    assert order.guest_access_token
    assert f"/checkout/success/{order.id}/{order.guest_access_token}/" in r.text
    assert client.session["guest_order_tokens"][str(order.id)] == order.guest_access_token


def test_guest_checkout_company_requires_auth(client, db):
    p, *_ = _prod()
    s = client.session
    s["cart"] = {str(p.id): {"qty": 1}}
    s.save()

    r = client.post(
        "/checkout/submit/",
        {
            "customer_type": "company",
            "payment_method": "cash",
        },
        HTTP_HX_REQUEST="true",
    )

    assert r.status_code == 422
    assert "войдите в аккаунт компании" in r.text


def test_guest_fake_payment_page_and_event_use_token(client, db):
    p, *_ = _prod()
    order = Order.objects.create(
        customer_type=Order.CustomerType.INDIVIDUAL,
        payment_method=Order.PaymentMethod.MIR_CARD,
        customer_name="Guest Buyer",
        customer_email="guest-pay@example.com",
        customer_phone="+79995550000",
        address_text="Guest pay street",
        guest_access_token="guesttoken123",
    )
    FakeAcquiringPayment.objects.create(
        order=order,
        amount=15,
        provider_payment_id=f"fake_guest_{order.id}",
        status=FakeAcquiringPayment.Status.PROCESSING,
        last_event=FakeAcquiringPayment.Event.START,
        history=[],
    )

    r_page = client.get(f"/payments/fake/{order.id}/{order.guest_access_token}/")
    assert r_page.status_code == 200
    assert "Тестовый эквайринг" in r_page.text

    r_event = client.post(
        f"/payments/fake/{order.id}/{order.guest_access_token}/event/",
        {"event": "success"},
        HTTP_HX_REQUEST="true",
    )
    assert r_event.status_code == 200
    order.refresh_from_db()
    assert order.status == Order.Status.PAID


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


def test_checkout_error_response_contains_tracking_payload(client, db):
    p, *_ = _prod()
    s = client.session
    s["cart"] = {str(p.id): {"qty": 1}}
    s.save()

    r = client.post(
        "/checkout/submit/",
        {
            "customer_type": "individual",
            "payment_method": "cash",
            "customer_name": "Guest Buyer",
            "customer_email": "guest@example.com",
            "customer_phone": "",
            "address_text": "",
        },
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 422
    assert "checkout_error" in r.text


def test_fake_payment_fail_returns_tracking_event(client_logged, user, db):
    order = Order.objects.create(
        customer_type=Order.CustomerType.INDIVIDUAL,
        payment_method=Order.PaymentMethod.MIR_CARD,
        customer_name="Ivan",
        customer_phone="+79999999999",
        address_text="Addr",
        placed_by=user,
    )
    FakeAcquiringPayment.objects.create(
        order=order,
        amount=15,
        provider_payment_id=f"fake_fail_{order.id}",
        status=FakeAcquiringPayment.Status.PROCESSING,
        last_event=FakeAcquiringPayment.Event.START,
        history=[],
    )

    r = client_logged.post(
        f"/payments/fake/{order.id}/event/",
        {"event": "fail"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    assert "payment_failed" in r.headers.get("HX-Trigger", "")


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


def test_product_page_renders_review_photos_and_public_questions(client_logged, user, db):
    p, *_ = _prod()
    review = ProductReview.objects.create(product=p, user=user, rating=5, text="With assets")
    ProductReviewPhoto.objects.create(review=review, image_url="https://example.com/review-photo.jpg", caption="Photo proof")
    ProductQuestion.objects.create(product=p, user=user, question_text="Есть ли сертификат?", is_public=True)

    r = client_logged.get(f"/product/{p.slug}/")
    assert r.status_code == 200
    assert "https://example.com/review-photo.jpg" in r.text
    assert "Photo proof" in r.text
    assert "Есть ли сертификат?" in r.text


def test_product_page_defers_heavy_recommendation_sections(client_logged, user, db):
    p, *_ = _prod()
    r = client_logged.get(f"/product/{p.slug}/")

    assert r.status_code == 200
    assert f'/product/{p.slug}/recommendations/fbt/' in r.text
    assert f'/product/{p.slug}/recommendations/seller-cross/' in r.text
    assert "Загружаем рекомендации" in r.text


def test_product_recommendation_section_endpoint_renders_partial(client_logged, user, db):
    p, *_ = _prod()
    r = client_logged.get(f"/product/{p.slug}/recommendations/fbt/", HTTP_HX_REQUEST="true")

    assert r.status_code == 200
    assert "product-reco-2026" in r.text


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


def test_product_review_marks_verified_purchase_and_accepts_vote(client_logged, user, db):
    p, *_ = _prod()
    buyer_order = Order.objects.create(
        customer_type=Order.CustomerType.INDIVIDUAL,
        payment_method=Order.PaymentMethod.CASH,
        customer_name="Ivan",
        customer_phone="+79999999999",
        address_text="Addr",
        placed_by=user,
        status=Order.Status.PAID,
    )
    buyer_order.items.create(product=p, name=p.name, price=p.price, qty=1)

    r_review = client_logged.post(f"/product/{p.slug}/review/", {"rating": "5", "text": "verified"})
    assert r_review.status_code in (302, 303)
    review = ProductReview.objects.get(product=p, user=user)
    assert review.is_verified_purchase is True

    from django.contrib.auth import get_user_model
    User = get_user_model()
    voter = User.objects.create_user(username="review_voter", password="pass")
    client_logged.force_login(voter)
    r_vote = client_logged.post(f"/product/{p.slug}/review/{review.id}/vote/", {"value": "helpful"}, HTTP_HX_REQUEST="true")
    assert r_vote.status_code == 200
    review.refresh_from_db()
    assert review.helpful_count == 1
    assert ProductReviewVote.objects.filter(review=review, user=voter, value=ProductReviewVote.Value.HELPFUL).exists()


def test_product_question_create(client_logged, user, db):
    p, *_ = _prod()
    r = client_logged.post(
        f"/product/{p.slug}/questions/",
        {"question_text": "Есть ли сертификат?"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    assert ProductQuestion.objects.filter(product=p, user=user, question_text__icontains="сертификат").exists()


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


def test_rating_visible_in_product_card_on_catalog(client_logged, user, db):
    p, *_ = _prod()
    ProductReview.objects.create(product=p, user=user, rating=4, text="ok")

    r = client_logged.get(f"/catalog/?q={p.name}")
    assert r.status_code == 200
    assert p.name in r.text
    assert "★" in r.text


def test_compare_toggle_and_compare_page(client, db):
    p1, *_ = _prod()
    brand = Brand.objects.create(name="CompareBrand")
    category = Category.objects.create(name="CompareCategory")
    p2 = Product.objects.create(sku="12345670", name="Compare 2", brand=brand, category=category, price=22, stock_qty=3)

    add_first = client.post("/compare/toggle/", {"product_id": p1.id})
    assert add_first.status_code == 200
    assert add_first.json()["in_compare"] is True
    assert add_first.json()["compare_count"] == 1

    add_second = client.post("/compare/toggle/", {"product_id": p2.id})
    assert add_second.status_code == 200
    assert add_second.json()["compare_count"] == 2

    page = client.get("/compare/")
    assert page.status_code == 200
    assert p1.name in page.text
    assert p2.name in page.text
    assert "Серия" in page.text
    assert "Сравнение товаров" in page.text


def test_compare_launcher_hidden_until_compare_has_items(client, db):
    p1, *_ = _prod()

    home = client.get("/")
    assert home.status_code == 200
    assert 'data-compare-launcher' in home.text
    assert 'hidden aria-hidden="true"' in home.text

    add = client.post("/compare/toggle/", {"product_id": p1.id})
    assert add.status_code == 200
    assert add.json()["compare_count"] == 1

    with_compare = client.get("/")
    assert with_compare.status_code == 200
    assert "data-compare-launcher" in with_compare.text
    assert "data-compare-badge" in with_compare.text
    assert 'hidden aria-hidden="true"' not in with_compare.text
    assert ">1<" in with_compare.text


def test_catalog_card_keeps_compare_and_favorite_actions_for_guest(client, db):
    product, *_ = _prod()

    response = client.get(f"/catalog/?q={product.name}")

    assert response.status_code == 200
    assert "data-compare-toggle" in response.text
    assert "/account/login/" in response.text
    assert 'action="/buy-now/"' in response.text
    assert "Купить в один клик" in response.text
    assert '<span class="ml-1">В корзину</span>' not in response.text


def test_buy_now_adds_product_and_redirects_to_checkout(client, db):
    product, *_ = _prod()

    response = client.post("/buy-now/", {"product_id": product.id, "qty": 1})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/checkout/")
    session = client.session
    assert session["cart"][str(product.id)]["qty"] == 1


def test_creator_can_edit_product_and_add_image_url(client, db):
    product, brand, category, _ = _prod()
    seller = get_user_model().objects.create_user(username="product_editor", password="pass")
    product.seller = seller
    product.save(update_fields=["seller"])

    assert client.login(username="product_editor", password="pass")
    response = client.post(
        f"/account/seller/products/{product.id}/edit/",
        {
            "sku": "12345671",
            "manufacturer_sku": "M-100",
            "name": "Updated product",
            "brand": brand.id,
            "category": category.id,
            "price": "99.00",
            "stock_qty": "12",
            "min_order_qty": "2",
            "lead_time_days": "3",
            "pack_qty": "4",
            "unit": "шт",
            "material": "Сталь",
            "purpose": "Кухня",
            "barcode": "1234567890",
            "description": "Updated description",
            "attributes_json": '{"Материал":"Сталь"}',
            "image_urls": "https://example.com/product.jpg",
        },
    )

    assert response.status_code == 302
    product.refresh_from_db()
    assert product.name == "Updated product"
    assert ProductImage.objects.filter(product=product, url="https://example.com/product.jpg").exists()


def test_admin_can_open_product_edit_page(client, db):
    product, *_ = _prod()
    get_user_model().objects.create_superuser(username="product_admin", email="admin@example.com", password="pass")
    assert client.login(username="product_admin", password="pass")

    response = client.get(f"/account/seller/products/{product.id}/edit/")

    assert response.status_code == 200
    assert "Редактирование карточки товара" in response.text
