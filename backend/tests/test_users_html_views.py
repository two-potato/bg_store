import pytest
import re
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils.datastructures import MultiValueDict
from orders.models import Order, OrderItem, SellerOrder, ShipmentItem, FakeAcquiringPayment, OrderSupportTicket
from orders.services import plan_seller_splits
from commerce.models import LegalEntity, LegalEntityMembership, DeliveryAddress, LegalEntityCreationRequest, SellerStore, MembershipRole, CompanyMembership, ApprovalPolicy
from users.models import UserProfile
from users.forms import SellerProductCreateForm, SellerProductImportForm
from catalog.models import Brand, Category, Product, ProductReview, ProductReviewComment, SellerOffer, SellerInventory, ProductQuestion, StockMovement
from orders.models import OrderClaim

pytestmark = pytest.mark.django_db


def test_account_home_auth_and_update(client, client_logged, user):
    # ensure anon for the first check (client_logged uses same client instance)
    client.logout()
    r0 = client.get("/account/")
    assert r0.status_code in (302, 303)
    # auth GET
    client.force_login(user)
    r1 = client.get("/account/")
    assert r1.status_code == 200
    # POST update
    r2 = client.post("/account/", {"contact_email": "new@example.com", "full_name": "Alice B", "phone": "+79999999999"})
    assert r2.status_code in (302, 303)
    profile = UserProfile.objects.get(user=user)
    assert profile.contact_email == "new@example.com"
    assert profile.full_name == "Alice B"
    assert profile.phone == "+79999999999"


def test_user_profile_created_automatically(client, db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    u = User.objects.create_user(username="auto_profile_u", password="pass")
    assert UserProfile.objects.filter(user=u).exists()


def test_user_email_syncs_to_profile_on_user_save(db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    u = User.objects.create_user(username="sync_u", password="pass", email="first@example.com")
    p = UserProfile.objects.get(user=u)
    assert p.contact_email == "first@example.com"

    u.email = "second@example.com"
    u.save(update_fields=["email"])
    p.refresh_from_db()
    assert p.contact_email == "second@example.com"


def test_profile_email_syncs_to_user_on_profile_save(db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    u = User.objects.create_user(username="sync_p", password="pass", email="user@example.com")
    p = UserProfile.objects.get(user=u)

    p.contact_email = "profile@example.com"
    p.save(update_fields=["contact_email"])
    u.refresh_from_db()
    assert u.email == "profile@example.com"


def test_account_addresses_htmx_flow(client_logged, user, db):
    le = LegalEntity.objects.create(name="LE1", inn="7707083893", bik="044525225", checking_account="40702810900000000001")
    LegalEntityMembership.objects.create(user=user, legal_entity=le)

    # GET fragment list
    r0 = client_logged.get("/account/addresses/?fragment=list", HTTP_HX_REQUEST="true")
    assert r0.status_code == 200

    # POST create valid address with HTMX
    payload = {
        "legal_entity": le.id,
        "label": "",
        "country": "RU",
        "city": "Msk",
        "street": "Lenina",
        "postcode": "101000",
        "is_default": True,
    }
    r1 = client_logged.post("/account/addresses/", payload, HTTP_HX_REQUEST="true")
    assert r1.status_code == 200  # returns partial list
    # invalid form -> errors branch
    bad = {"legal_entity": le.id, "label": ""}
    r2 = client_logged.post("/account/addresses/", bad, HTTP_HX_REQUEST="true")
    assert r2.status_code == 200


def test_account_legal_entities_flow(client_logged, user, db):
    # GET base
    r0 = client_logged.get("/account/legal/")
    assert r0.status_code == 200
    # POST create request
    payload = {
        "name": "Proj",
        "inn": "7707083893",
        "phone": "+70000000000",
        "bik": "044525225",
        "checking_account": "40702810900000000001",
        "bank_name": "SBER",
        "confirm": True,
    }
    r1 = client_logged.post("/account/legal/", payload)
    assert r1.status_code in (200, 302, 303)
    # invalid form -> error message branch
    bad = {"name": "", "inn": "", "confirm": False}
    r1b = client_logged.post("/account/legal/", bad)
    assert r1b.status_code == 200
    # HTMX fragments
    r2 = client_logged.get("/account/legal/?fragment=requests", HTTP_HX_REQUEST="true")
    assert r2.status_code == 200
    r3 = client_logged.get("/account/legal/?fragment=memberships", HTTP_HX_REQUEST="true")
    assert r3.status_code == 200


def test_cancel_legal_request(client_logged, user, db):
    req = LegalEntityCreationRequest.objects.create(applicant=user, name="N", inn="7707083893", bik="044525225", checking_account="40702810900000000001")
    r = client_logged.post(f"/account/legal/request/{req.id}/cancel/")
    assert r.status_code == 200


def test_account_orders_page(client_logged, user, db):
    le = LegalEntity.objects.create(name="LE2", inn="5408131553", bik="044525225", checking_account="40702810900000000003")
    addr = DeliveryAddress.objects.create(legal_entity=le, label="Ofc", country="RU", city="Msk", street="Lenina", postcode="101000")
    Order.objects.create(legal_entity=le, placed_by=user, delivery_address=addr)
    r = client_logged.get("/account/orders/")
    assert r.status_code == 200


def test_account_order_detail_owner_only(client, client_logged, user, db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    other = User.objects.create_user(username="u2", password="pass")
    le = LegalEntity.objects.create(name="LE3", inn="7715964180", bik="044525225", checking_account="40702810900000000004")
    addr = DeliveryAddress.objects.create(legal_entity=le, label="WH", country="RU", city="SPB", street="Nevsky", postcode="190000")
    own_order = Order.objects.create(legal_entity=le, placed_by=user, delivery_address=addr)
    other_order = Order.objects.create(legal_entity=le, placed_by=other, delivery_address=addr)

    r1 = client_logged.get(f"/account/orders/{own_order.id}/")
    assert r1.status_code == 200

    r2 = client_logged.get(f"/account/orders/{other_order.id}/")
    assert r2.status_code == 404


def test_account_comments_page_lists_only_user_comments(client_logged, user, db):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    product = Product.objects.create(sku="12345678", name="Test product")
    own_review = ProductReview.objects.create(product=product, user=user, rating=5, text="Good")
    ProductReviewComment.objects.create(review=own_review, user=user, text="Мой комментарий")

    other = User.objects.create_user(username="u3", password="pass")
    other_review = ProductReview.objects.create(product=product, user=other, rating=4, text="Other")
    ProductReviewComment.objects.create(review=other_review, user=other, text="Чужой комментарий")

    r = client_logged.get("/account/comments/")
    assert r.status_code == 200
    assert "Мой комментарий" in r.text
    assert "Чужой комментарий" not in r.text


def test_login_register_logout(client, user, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    from django.contrib.auth import get_user_model
    User = get_user_model()
    # login GET
    r0 = client.get("/account/login/")
    assert r0.status_code == 200
    # invalid credentials
    r1 = client.post("/account/login/", {"identifier": user.username, "password": "bad"})
    assert r1.status_code == 200
    # valid
    r2 = client.post("/account/login/", {"identifier": user.username, "password": "pass"})
    assert r2.status_code in (302, 303)
    client.get("/account/logout/")
    # register
    r3 = client.get("/account/register/")
    assert r3.status_code in (200, 302, 303)
    r4 = client.post("/account/register/", {
        "username": "newuser",
        "email": "newuser@example.com",
        "password1": "p@ss12345",
        "password2": "p@ss12345",
    })
    assert r4.status_code in (302, 303)
    assert r4.headers.get("Location", "").endswith("/account/login/")
    new_user = User.objects.get(username="newuser")
    assert new_user.is_active is False
    assert len(mail.outbox) >= 1
    body = mail.outbox[-1].body
    m = re.search(r"/account/confirm-email/\?token=([^\s]+)", body)
    assert m, body
    token = m.group(1)
    assert token.count(":") >= 3
    assert token.count(".") != 2

    # cannot login before email confirmation
    r_pre = client.post("/account/login/", {"identifier": "newuser@example.com", "password": "p@ss12345"})
    assert r_pre.status_code == 200

    # confirm email via one-time signed link and get authenticated session
    r_confirm = client.get(f"/account/confirm-email/?token={token}")
    assert r_confirm.status_code in (302, 303)
    assert r_confirm.headers.get("Location", "").startswith("/account/")
    new_user.refresh_from_db()
    assert new_user.is_active is True
    assert "_auth_user_id" in client.session
    assert str(new_user.id) == client.session["_auth_user_id"]

    reused = client.get(f"/account/confirm-email/?token={token}", follow=True)
    assert reused.status_code == 200
    assert "уже использована" in reused.text or "недействительна" in reused.text

    # logout
    r5 = client.get("/account/logout/")
    assert r5.status_code in (302, 303)


def test_login_uses_generic_error_for_inactive_user(client, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    from django.contrib.auth import get_user_model

    User = get_user_model()
    inactive_user = User.objects.create_user(
        username="inactive-user",
        email="inactive@example.com",
        password="pass12345",
        is_active=False,
    )

    response = client.post(
        "/account/login/",
        {"identifier": inactive_user.email, "password": "pass12345"},
        follow=True,
    )

    assert response.status_code == 200
    assert "Неверные учётные данные" in response.text
    assert "Подтвердите email" not in response.text


def test_login_ignores_external_next_redirect(client, user):
    r = client.post(
        "/account/login/?next=https://evil.example/phish",
        {"identifier": user.username, "password": "pass"},
    )
    assert r.status_code in (302, 303)
    assert r.headers.get("Location", "").startswith("/account/")


def test_login_page_google_button_state(client, settings):
    settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]["client_id"] = ""
    r_disabled = client.get("/account/login/")
    assert r_disabled.status_code == 200
    assert "Войти через Google (не настроено)" in r_disabled.text

    settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]["client_id"] = "client-id"
    r_enabled = client.get("/account/login/")
    assert r_enabled.status_code == 200
    assert "/account/social/google/login/" in r_enabled.text


def test_register_page_google_button_state(client, settings):
    settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]["client_id"] = ""
    r_disabled = client.get("/account/register/")
    assert r_disabled.status_code == 200
    assert "Зарегистрироваться через Google (не настроено)" in r_disabled.text

    settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]["client_id"] = "client-id"
    r_enabled = client.get("/account/register/")
    assert r_enabled.status_code == 200
    assert "/account/social/google/login/" in r_enabled.text


def test_twa_login_flow(monkeypatch, client):
    # no initData -> redirect with message
    r0 = client.get("/account/twa/login/")
    assert r0.status_code in (302, 303)
    # valid flow
    from users.views import auth_html as auth_views

    monkeypatch.setattr(auth_views, "verify_init_data", lambda _: {"id": 1, "username": "tg"})
    r1 = client.get("/account/twa/login/?initData=dummy")
    assert r1.status_code in (302, 303)


def test_seller_cabinet_and_product_add(client_logged, user, db):
    profile = UserProfile.objects.get(user=user)
    profile.role = UserProfile.Role.SELLER
    profile.save(update_fields=["role"])

    le = LegalEntity.objects.create(name="Seller LE", inn="7703897659", bik="044525225", checking_account="40702810900000000011")
    LegalEntityMembership.objects.create(user=user, legal_entity=le)

    r0 = client_logged.get("/account/seller/")
    assert r0.status_code == 200

    r1 = client_logged.post("/account/seller/", {"name": "Мой магазин", "legal_entity": le.id})
    assert r1.status_code in (302, 303)
    assert SellerStore.objects.filter(owner=user, name="Мой магазин", legal_entity=le).exists()

    brand = Brand.objects.create(name="SellerBrand")
    category = Category.objects.create(name="SellerCategory")
    payload = {
        "sku": "98765432",
        "name": "Seller product",
        "brand": brand.id,
        "category": category.id,
        "price": "199.99",
        "stock_qty": 25,
        "description": "Desc",
        "is_new": "on",
    }
    r2 = client_logged.post("/account/seller/products/add/", payload)
    assert r2.status_code in (302, 303)
    product = Product.objects.get(sku="98765432")
    assert product.seller_id == user.id


def test_non_seller_cannot_open_seller_pages(client_logged):
    r0 = client_logged.get("/account/seller/")
    assert r0.status_code in (302, 303)
    r1 = client_logged.get("/account/seller/products/add/")
    assert r1.status_code in (302, 303)


def test_auth_templates_have_htmx_validation_and_password_toggles(client):
    login_page = client.get("/account/login/")
    assert login_page.status_code == 200
    assert '/account/login/validate/' in login_page.text
    assert "data-password-toggle" in login_page.text
    assert "data-password-input" in login_page.text

    register_page = client.get("/account/register/")
    assert register_page.status_code == 200
    assert '/account/register/validate/' in register_page.text
    # two password fields on registration form
    assert register_page.text.count("data-password-toggle") >= 2


def test_auth_validate_endpoints_return_form_errors(client):
    login_validate = client.post(
        "/account/login/validate/",
        {"identifier": "", "password": ""},
        HTTP_HX_REQUEST="true",
    )
    assert login_validate.status_code == 200
    assert "Обязательное поле" in login_validate.text

    register_validate = client.post(
        "/account/register/validate/",
        {"username": "", "email": "bad", "password1": "1", "password2": "2"},
        HTTP_HX_REQUEST="true",
    )
    assert register_validate.status_code == 200
    assert "Пароли не совпадают" in register_validate.text


def test_login_requires_captcha_after_failed_attempts(client, user, settings, monkeypatch):
    settings.LOGIN_CAPTCHA_THRESHOLD = 1
    settings.LOGIN_CAPTCHA_WINDOW_SECONDS = 300
    settings.TURNSTILE_SITE_KEY = "site-key"
    settings.TURNSTILE_SECRET_KEY = "secret-key"

    # first failed attempt should arm captcha
    failed = client.post("/account/login/", {"identifier": user.username, "password": "bad"})
    assert failed.status_code == 200

    page_with_captcha = client.get("/account/login/")
    assert page_with_captcha.status_code == 200
    assert "cf-turnstile" in page_with_captcha.text
    assert 'data-sitekey="site-key"' in page_with_captcha.text

    from users import views_auth_html as vauth
    monkeypatch.setattr(vauth, "_verify_turnstile", lambda token, remoteip: (False, "captcha error"))

    blocked = client.post(
        "/account/login/",
        {"identifier": user.username, "password": "pass"},
    )
    assert blocked.status_code == 200
    assert "captcha error" in blocked.text


def test_seller_orders_pages_and_actions(client_logged, user, db):
    profile = UserProfile.objects.get(user=user)
    profile.role = UserProfile.Role.SELLER
    profile.save(update_fields=["role"])

    le = LegalEntity.objects.create(name="Seller Ops LE", inn="7707083894", bik="044525225", checking_account="40702810900000000021")
    LegalEntityMembership.objects.create(user=user, legal_entity=le)
    SellerStore.objects.create(owner=user, legal_entity=le, name="Ops Store")

    buyer = user.__class__.objects.create_user(username="buyer_ops", password="pass")
    product = Product.objects.create(sku="12344321", name="Ops Product", price="100.00", stock_qty=10, seller=user)
    order = Order.objects.create(
        placed_by=buyer,
        requested_by=buyer,
        legal_entity=le,
        customer_type=Order.CustomerType.COMPANY,
        payment_method=Order.PaymentMethod.INVOICE,
    )
    OrderItem.objects.create(order=order, product=product, name=product.name, price=product.price, qty=2)
    plan_seller_splits(order)
    seller_order = SellerOrder.objects.get(order=order, seller=user)

    r0 = client_logged.get("/account/seller/orders/")
    assert r0.status_code == 200
    assert f"Seller order #{seller_order.id}" in r0.text

    r1 = client_logged.get(f"/account/seller/orders/{seller_order.id}/")
    assert r1.status_code == 200

    r2 = client_logged.post(f"/account/seller/orders/{seller_order.id}/status/", {"status": SellerOrder.Status.ACCEPTED})
    assert r2.status_code in (302, 303)
    seller_order.refresh_from_db()
    assert seller_order.status == SellerOrder.Status.ACCEPTED

    shipment = seller_order.shipments.first()
    r2b = client_logged.post(
        f"/account/seller/orders/{seller_order.id}/shipments/{shipment.id}/items/",
        {f"item_{seller_order.items.get().id}_qty": "2"},
    )
    assert r2b.status_code in (302, 303)
    r3 = client_logged.post(
        f"/account/seller/orders/{seller_order.id}/shipments/{shipment.id}/",
        {"tracking_number": "TRACK-1", "delivery_method": "courier", "warehouse_name": "WH-1", "status": "in_transit"},
    )
    assert r3.status_code in (302, 303)
    shipment.refresh_from_db()
    assert shipment.tracking_number == "TRACK-1"
    assert shipment.status == "in_transit"


def test_buyer_reorder_cancel_and_approval_inbox(client_logged, user, db):
    buyer = user
    seller = user.__class__.objects.create_user(username="seller_ops_2", password="pass")
    seller_profile = UserProfile.objects.get(user=seller)
    seller_profile.role = UserProfile.Role.SELLER
    seller_profile.save(update_fields=["role"])

    le = LegalEntity.objects.create(name="Buyer LE", inn="7707083895", bik="044525225", checking_account="40702810900000000031")
    owner_role, _ = MembershipRole.objects.get_or_create(code="owner", defaults={"name": "Owner"})
    LegalEntityMembership.objects.create(user=buyer, legal_entity=le, role=owner_role)
    SellerStore.objects.create(owner=seller, legal_entity=le, name="Ops Store 2")

    product = Product.objects.create(sku="87654321", name="Repeatable", price="50.00", stock_qty=20, seller=seller)
    order = Order.objects.create(
        placed_by=buyer,
        requested_by=buyer,
        legal_entity=le,
        approval_status=Order.ApprovalStatus.PENDING,
        customer_type=Order.CustomerType.COMPANY,
        payment_method=Order.PaymentMethod.INVOICE,
    )
    OrderItem.objects.create(order=order, product=product, name=product.name, price=product.price, qty=3)
    plan_seller_splits(order)

    r0 = client_logged.post(f"/account/orders/{order.id}/reorder/")
    assert r0.status_code in (302, 303)
    session = client_logged.session
    assert session["cart"][str(product.id)]["qty"] >= 3

    r1 = client_logged.post(f"/account/orders/{order.id}/cancel/")
    assert r1.status_code in (302, 303)
    order.refresh_from_db()
    assert order.status == Order.Status.CANCELED

    pending = Order.objects.create(
        placed_by=buyer,
        requested_by=buyer,
        legal_entity=le,
        approval_status=Order.ApprovalStatus.PENDING,
        customer_type=Order.CustomerType.COMPANY,
        payment_method=Order.PaymentMethod.INVOICE,
    )
    r2 = client_logged.get("/account/approvals/")
    assert r2.status_code == 200
    assert f"Заказ #{pending.id}" in r2.text


def test_seller_offers_and_inventory_pages(client_logged, user, db):
    profile = UserProfile.objects.get(user=user)
    profile.role = UserProfile.Role.SELLER
    profile.save(update_fields=["role"])

    le = LegalEntity.objects.create(name="Seller Offer LE", inn="7707083896", bik="044525225", checking_account="40702810900000000041")
    LegalEntityMembership.objects.create(user=user, legal_entity=le)
    SellerStore.objects.create(owner=user, legal_entity=le, name="Offer Store")
    product = Product.objects.create(sku="11223344", name="Offer Product", price="75.00", stock_qty=9, seller=user)

    r0 = client_logged.get("/account/seller/offers/")
    assert r0.status_code == 200

    r1 = client_logged.post(
        "/account/seller/offers/",
        {"product": product.id, "offer_title": "Special offer", "price": "69.00", "min_order_qty": 2, "lead_time_days": 1, "status": "active", "warehouse_source": "Main"},
    )
    assert r1.status_code in (302, 303)
    offer = SellerOffer.objects.get(product=product, seller=user)
    assert offer.price == 69

    r2 = client_logged.post(
        f"/account/seller/offers/{offer.id}/",
        {"action": "add_inventory", "inventory-warehouse_name": "WH-1", "inventory-warehouse_code": "A1", "inventory-stock_qty": 15, "inventory-reserved_qty": 3, "inventory-incoming_qty": 2, "inventory-eta_days": 1, "inventory-is_primary": "on"},
    )
    assert r2.status_code in (302, 303)
    inv = SellerInventory.objects.get(offer=offer, warehouse_name="WH-1")
    assert inv.is_primary is True


def test_seller_can_answer_product_questions(client_logged, user, db):
    profile = UserProfile.objects.get(user=user)
    profile.role = UserProfile.Role.SELLER
    profile.save(update_fields=["role"])

    le = LegalEntity.objects.create(name="Seller Q LE", inn="7707083897", bik="044525225", checking_account="40702810900000000051")
    LegalEntityMembership.objects.create(user=user, legal_entity=le)
    SellerStore.objects.create(owner=user, legal_entity=le, name="Question Store")
    buyer = user.__class__.objects.create_user(username="qbuyer", password="pass")
    product = Product.objects.create(sku="44332211", name="Question Product", price="55.00", stock_qty=5, seller=user)
    question = ProductQuestion.objects.create(product=product, user=buyer, question_text="Есть ли сертификат?", is_public=True)

    r0 = client_logged.get("/account/seller/questions/")
    assert r0.status_code == 200
    assert "Есть ли сертификат?" in r0.text

    r1 = client_logged.post(
        f"/account/seller/questions/{question.id}/answer/",
        {"answer_text": "Да, сертификат приложим к поставке", "is_public": "on"},
    )
    assert r1.status_code in (302, 303)
    question.refresh_from_db()
    assert "сертификат" in question.answer_text.lower()
    assert question.answered_by_id == user.id


def test_seller_can_reply_to_review_and_filter_orders(client_logged, user, db):
    profile = UserProfile.objects.get(user=user)
    profile.role = UserProfile.Role.SELLER
    profile.save(update_fields=["role"])

    le = LegalEntity.objects.create(name="Seller Review LE", inn="7707083898", bik="044525225", checking_account="40702810900000000061")
    LegalEntityMembership.objects.create(user=user, legal_entity=le)
    SellerStore.objects.create(owner=user, legal_entity=le, name="Review Store")
    buyer = user.__class__.objects.create_user(username="reviewbuyer", password="pass", email="review@example.com")
    product = Product.objects.create(sku="99887766", name="Review Product", price="44.00", stock_qty=12, seller=user)
    review = ProductReview.objects.create(product=product, user=buyer, rating=5, text="Отличный товар")

    r0 = client_logged.get("/account/seller/reviews/")
    assert r0.status_code == 200
    assert "Отличный товар" in r0.text

    r1 = client_logged.post(f"/account/seller/reviews/{review.id}/reply/", {f"review-{review.id}-text": "Спасибо за отзыв"})
    assert r1.status_code in (302, 303)
    assert ProductReviewComment.objects.filter(review=review, user=user, text__icontains="Спасибо").exists()

    order = Order.objects.create(
        placed_by=buyer,
        requested_by=buyer,
        legal_entity=le,
        customer_name="Review Buyer",
        customer_email="review@example.com",
        customer_type=Order.CustomerType.COMPANY,
        payment_method=Order.PaymentMethod.INVOICE,
    )
    OrderItem.objects.create(order=order, product=product, name=product.name, price=product.price, qty=1)
    plan_seller_splits(order)
    r2 = client_logged.get("/account/seller/orders/?sku=99887766&customer=review@example.com")
    assert r2.status_code == 200
    assert "Seller order #" in r2.text


def test_company_member_self_service_and_order_claims(client_logged, user, db):
    owner = user
    owner_role, _ = MembershipRole.objects.get_or_create(code="owner", defaults={"name": "Owner"})
    le = LegalEntity.objects.create(name="Managed Co", inn="7707083899", bik="044525225", checking_account="40702810900000000071")
    LegalEntityMembership.objects.create(user=owner, legal_entity=le, role=owner_role)

    from commerce.company_service import ensure_company_workspace
    company = ensure_company_workspace(le)
    CompanyMembership.objects.update_or_create(user=owner, company=company, defaults={"role": CompanyMembership.Role.OWNER})

    teammate = owner.__class__.objects.create_user(username="member_ops", password="pass", email="member@example.com")

    r0 = client_logged.post(
        f"/account/legal/company/{company.id}/",
        {
            "action": "invite_member",
            "invite-identifier": "member_ops",
            "invite-role": CompanyMembership.Role.APPROVER,
            "invite-approval_limit": "1500.00",
            "invite-is_default_approver": "on",
        },
    )
    assert r0.status_code in (302, 303)
    membership = CompanyMembership.objects.get(user=teammate, company=company)
    assert membership.role == CompanyMembership.Role.APPROVER
    assert LegalEntityMembership.objects.filter(user=teammate, legal_entity=le).exists()

    r1 = client_logged.post(
        f"/account/legal/company/{company.id}/",
        {
            "action": "update_member",
            "member_id": membership.id,
            f"member-{membership.id}-role": CompanyMembership.Role.BUYER,
            f"member-{membership.id}-approval_limit": "0",
        },
    )
    assert r1.status_code in (302, 303)
    membership.refresh_from_db()
    assert membership.role == CompanyMembership.Role.BUYER

    seller = owner.__class__.objects.create_user(username="claimseller", password="pass")
    seller_profile = UserProfile.objects.get(user=seller)
    seller_profile.role = UserProfile.Role.SELLER
    seller_profile.save(update_fields=["role"])
    SellerStore.objects.create(owner=seller, legal_entity=le, name="Claim Store")
    product = Product.objects.create(sku="66778899", name="Claim Product", price="31.00", stock_qty=4, seller=seller)
    order = Order.objects.create(
        placed_by=owner,
        requested_by=owner,
        legal_entity=le,
        customer_type=Order.CustomerType.COMPANY,
        payment_method=Order.PaymentMethod.INVOICE,
    )
    OrderItem.objects.create(order=order, product=product, name=product.name, price=product.price, qty=1)

    r2 = client_logged.post(
        f"/account/orders/{order.id}/claims/",
        {"claim_type": "delivery", "message": "Поставку нужно ускорить"},
    )
    assert r2.status_code in (302, 303)
    assert OrderClaim.objects.filter(order=order, created_by=owner, claim_type="delivery").exists()
    claim = OrderClaim.objects.get(order=order, created_by=owner)

    seller_client = Client()
    seller_client.force_login(seller)
    seller_order = SellerOrder.objects.get(order=order, seller=seller)
    r3 = seller_client.post(
        f"/account/seller/orders/{seller_order.id}/claims/{claim.id}/",
        {"status": "in_review", "seller_response": "Проверяем SLA доставки", "resolution_comment": ""},
    )
    assert r3.status_code in (302, 303)
    claim.refresh_from_db()
    assert claim.status == OrderClaim.Status.IN_REVIEW
    assert claim.seller_response == "Проверяем SLA доставки"

    r4 = client_logged.post(
        f"/account/legal/company/{company.id}/",
        {
            "action": "save_company_settings",
            "company-display_name": "Managed Co HQ",
            "company-procurement_email": "proc@example.com",
            "company-procurement_phone": "+70000000000",
            "company-invoice_email": "invoice@example.com",
            "company-preferred_payment_method": "invoice",
            "company-payment_comment": "Оплата по счёту 5 банковских дней",
            "company-is_active": "on",
        },
    )
    assert r4.status_code in (302, 303)
    company.refresh_from_db()
    assert company.invoice_email == "invoice@example.com"

    r5 = client_logged.post(
        f"/account/legal/company/{company.id}/",
        {
            "action": "add_contact",
            "contact-name": "Finance Lead",
            "contact-email": "finance@example.com",
            "contact-phone": "+71111111111",
            "contact-role": "finance",
            "contact-is_default": "on",
            "contact-notes": "Primary billing contact",
        },
    )
    assert r5.status_code in (302, 303)
    assert "Finance Lead" in client_logged.get(f"/account/legal/company/{company.id}/").text


def test_seller_can_create_partial_shipments_and_cancel_item_qty(client_logged, user, db):
    profile = UserProfile.objects.get(user=user)
    profile.role = UserProfile.Role.SELLER
    profile.save(update_fields=["role"])

    le = LegalEntity.objects.create(name="Seller Fulfillment LE", inn="7707083800", bik="044525225", checking_account="40702810900000000081")
    LegalEntityMembership.objects.create(user=user, legal_entity=le)
    SellerStore.objects.create(owner=user, legal_entity=le, name="Fulfillment Store")
    buyer = user.__class__.objects.create_user(username="fulfillbuyer", password="pass")
    product = Product.objects.create(sku="55667788", name="Fulfillment Product", price="20.00", stock_qty=9, seller=user)
    order = Order.objects.create(
        placed_by=buyer,
        requested_by=buyer,
        legal_entity=le,
        customer_type=Order.CustomerType.COMPANY,
        payment_method=Order.PaymentMethod.INVOICE,
    )
    OrderItem.objects.create(order=order, product=product, name=product.name, price=product.price, qty=5)
    plan_seller_splits(order)
    seller_order = SellerOrder.objects.get(order=order, seller=user)
    seller_item = seller_order.items.get()

    r0 = client_logged.post(
        f"/account/seller/orders/{seller_order.id}/shipments/create/",
        {"warehouse_name": "WH-2", "delivery_method": "courier"},
    )
    assert r0.status_code in (302, 303)
    extra_shipment = seller_order.shipments.order_by("-id").first()

    base_shipment = seller_order.shipments.order_by("id").first()
    r1 = client_logged.post(
        f"/account/seller/orders/{seller_order.id}/shipments/{base_shipment.id}/items/",
        {f"item_{seller_item.id}_qty": "2"},
    )
    assert r1.status_code in (302, 303)
    assert ShipmentItem.objects.get(shipment=base_shipment, seller_order_item=seller_item).qty == 2

    r2 = client_logged.post(
        f"/account/seller/orders/{seller_order.id}/shipments/{extra_shipment.id}/items/",
        {f"item_{seller_item.id}_qty": "3"},
    )
    assert r2.status_code in (302, 303)
    assert ShipmentItem.objects.get(shipment=extra_shipment, seller_order_item=seller_item).qty == 3

    r3 = client_logged.post(
        f"/account/seller/orders/{seller_order.id}/items/{seller_item.id}/cancel/",
        {"seller_order_item_id": seller_item.id, "cancel_qty": "2"},
    )
    assert r3.status_code in (302, 303)
    seller_item.refresh_from_db()
    seller_item.order_item.refresh_from_db()
    assert seller_item.canceled_qty == 2
    assert seller_item.order_item.canceled_qty == 2
    assert ShipmentItem.objects.get(shipment=base_shipment, seller_order_item=seller_item).qty == 2
    assert ShipmentItem.objects.get(shipment=extra_shipment, seller_order_item=seller_item).qty == 1


def test_seller_can_adjust_reserve_and_view_stock_history(client_logged, user, db):
    profile = UserProfile.objects.get(user=user)
    profile.role = UserProfile.Role.SELLER
    profile.save(update_fields=["role"])

    le = LegalEntity.objects.create(name="Seller Stock LE", inn="7707083801", bik="044525225", checking_account="40702810900000000082")
    LegalEntityMembership.objects.create(user=user, legal_entity=le)
    SellerStore.objects.create(owner=user, legal_entity=le, name="Stock Store")
    product = Product.objects.create(sku="22113344", name="Stock Product", price="90.00", stock_qty=18, seller=user)
    offer = SellerOffer.objects.create(product=product, seller=user, seller_store=user.seller_store, price="85.00")
    inventory = SellerInventory.objects.create(offer=offer, warehouse_name="Main WH", stock_qty=10, reserved_qty=1, incoming_qty=0, is_primary=True)

    r0 = client_logged.post(
        f"/account/seller/offers/{offer.id}/inventories/{inventory.id}/adjust/",
        {
            "adjust-inventory_id": inventory.id,
            "adjust-field_type": "reserved",
            "adjust-delta": "3",
            "adjust-reason": "reserve for wholesale request",
        },
    )
    assert r0.status_code in (302, 303)
    inventory.refresh_from_db()
    assert inventory.reserved_qty == 4
    movement = StockMovement.objects.get(inventory=inventory)
    assert movement.after_value == 4

    r1 = client_logged.get(f"/account/seller/offers/{offer.id}/")
    assert r1.status_code == 200
    assert "История движения остатков" in r1.text
    assert "reserve for wholesale request" in r1.text


def test_seller_bulk_product_actions_and_csv_import(client_logged, user, db):
    profile = UserProfile.objects.get(user=user)
    profile.role = UserProfile.Role.SELLER
    profile.save(update_fields=["role"])

    le = LegalEntity.objects.create(name="Seller Import LE", inn="7707083802", bik="044525225", checking_account="40702810900000000083")
    LegalEntityMembership.objects.create(user=user, legal_entity=le)
    SellerStore.objects.create(owner=user, legal_entity=le, name="Import Store")
    brand = Brand.objects.create(name="Bulk Brand")
    category = Category.objects.create(name="Bulk Category")
    product = Product.objects.create(
        sku="33112244",
        name="Bulk Product",
        brand=brand,
        category=category,
        price="120.00",
        stock_qty=8,
        seller=user,
    )

    r0 = client_logged.get("/account/seller/products/template/")
    assert r0.status_code == 200
    assert "sku,name,brand,category" in r0.text

    r1 = client_logged.post(
        "/account/seller/products/add/",
        {
            "workflow": "bulk_update",
            "action": "add_stock",
            "stock_delta": "5",
            "product_ids": [str(product.id)],
        },
    )
    assert r1.status_code in (302, 303)
    product.refresh_from_db()
    assert product.stock_qty == 13

    csv_payload = (
        "sku,name,brand,category,manufacturer_sku,price,stock_qty,min_order_qty,lead_time_days,material,purpose,description,is_new,is_promo\n"
        "44556677,CSV Product,CSV Brand,CSV Category,CSV-1,99.90,17,2,4,Steel,Kitchen,Imported row,1,0\n"
        "33112244,Bulk Product Updated,Bulk Brand,Bulk Category,CSV-2,140.00,21,1,2,Glass,Bar,Updated row,0,1\n"
    ).encode("utf-8")
    upload = SimpleUploadedFile("catalog.csv", csv_payload, content_type="text/csv")
    r2 = client_logged.post(
        "/account/seller/products/add/",
        {"workflow": "import_catalog", "csv_file": upload},
    )
    assert r2.status_code in (302, 303)
    imported = Product.objects.get(sku="44556677", seller=user)
    assert imported.name == "CSV Product"
    product.refresh_from_db()
    assert product.name == "Bulk Product Updated"
    assert product.is_promo is True

    bad_upload = SimpleUploadedFile("bad.csv", b"sku,name\n123,Bad row\n", content_type="text/csv")
    r3 = client_logged.post(
        "/account/seller/products/add/",
        {"workflow": "import_catalog", "csv_file": bad_upload},
        follow=True,
    )
    assert r3.status_code == 200
    assert "Ошибки импорта" in r3.text or "ошибки валидации" in r3.text.lower()


def test_company_policy_multistep_approval_and_support_retry_payment(client_logged, user, db):
    owner = user
    owner_role, _ = MembershipRole.objects.get_or_create(code="owner", defaults={"name": "Owner"})
    approver_role, _ = MembershipRole.objects.get_or_create(code="manager", defaults={"name": "Менеджер"})
    le = LegalEntity.objects.create(name="Approval Co", inn="7707083803", bik="044525225", checking_account="40702810900000000084")
    LegalEntityMembership.objects.create(user=owner, legal_entity=le, role=owner_role)

    from commerce.company_service import ensure_company_workspace
    company = ensure_company_workspace(le)
    CompanyMembership.objects.update_or_create(user=owner, company=company, defaults={"role": CompanyMembership.Role.OWNER})

    approver_one = owner.__class__.objects.create_user(username="approver_one", password="pass", email="a1@example.com")
    approver_two = owner.__class__.objects.create_user(username="approver_two", password="pass", email="a2@example.com")
    CompanyMembership.objects.create(user=approver_one, company=company, role=CompanyMembership.Role.APPROVER)
    CompanyMembership.objects.create(user=approver_two, company=company, role=CompanyMembership.Role.APPROVER)
    LegalEntityMembership.objects.create(user=approver_one, legal_entity=le, role=approver_role)
    LegalEntityMembership.objects.create(user=approver_two, legal_entity=le, role=approver_role)

    r0 = client_logged.post(
        f"/account/legal/company/{company.id}/",
        {
            "action": "update_policy",
            "policy-is_enabled": "on",
            "policy-auto_approve_below": "0",
            "policy-required_approvals_count": "2",
            "policy-max_pending_hours": "48",
            "policy-require_approver_role": "on",
            "policy-require_comment": "on",
        },
    )
    assert r0.status_code in (302, 303)
    policy = ApprovalPolicy.objects.get(company=company)
    assert policy.required_approvals_count == 2
    assert policy.require_comment is True

    seller = owner.__class__.objects.create_user(username="support_seller", password="pass")
    seller_profile = UserProfile.objects.get(user=seller)
    seller_profile.role = UserProfile.Role.SELLER
    seller_profile.save(update_fields=["role"])
    SellerStore.objects.create(owner=seller, legal_entity=le, name="Support Seller Store")
    product = Product.objects.create(sku="77889900", name="Approval Product", price="70.00", stock_qty=5, seller=seller)
    order = Order.objects.create(
        placed_by=owner,
        requested_by=owner,
        legal_entity=le,
        approval_status=Order.ApprovalStatus.PENDING,
        customer_type=Order.CustomerType.COMPANY,
        payment_method=Order.PaymentMethod.MIR_CARD,
    )
    OrderItem.objects.create(order=order, product=product, name=product.name, price=product.price, qty=1)
    plan_seller_splits(order)
    FakeAcquiringPayment.objects.create(
        order=order,
        amount=order.total,
        provider_payment_id=f"retry-{order.id}",
        status=FakeAcquiringPayment.Status.FAILED,
        last_event=FakeAcquiringPayment.Event.FAIL,
    )

    approver_client = Client()
    approver_client.force_login(approver_one)
    r1 = approver_client.post(f"/account/orders/{order.id}/approval/", {"action": "approve", "comment": "Первый аппрув"})
    assert r1.status_code in (302, 303)
    order.refresh_from_db()
    assert order.approval_status == Order.ApprovalStatus.PENDING

    approver_client_2 = Client()
    approver_client_2.force_login(approver_two)
    r2 = approver_client_2.post(f"/account/orders/{order.id}/approval/", {"action": "approve", "comment": "Второй аппрув"})
    assert r2.status_code in (302, 303)
    order.refresh_from_db()
    assert order.approval_status == Order.ApprovalStatus.APPROVED

    r3 = client_logged.post(
        f"/account/orders/{order.id}/support/",
        {"topic": "payment", "subject": "Не прошла оплата", "message": "Нужно повторить оплату заказа"},
    )
    assert r3.status_code in (302, 303)
    ticket = OrderSupportTicket.objects.get(order=order, created_by=owner)
    assert ticket.topic == "payment"

    seller_order = SellerOrder.objects.get(order=order, seller=seller)
    seller_client = Client()
    seller_client.force_login(seller)
    r4 = seller_client.post(
        f"/account/seller/orders/{seller_order.id}/support/{ticket.id}/",
        {"status": "resolved", "resolution_comment": "Платёж можно повторить из кабинета"},
    )
    assert r4.status_code in (302, 303)
    ticket.refresh_from_db()
    assert ticket.status == "resolved"

    r5 = client_logged.get(f"/account/orders/{order.id}/retry-payment/")
    assert r5.status_code in (302, 303)
    assert r5.headers["Location"].endswith(f"/payments/fake/{order.id}/")


def test_seller_product_form_rejects_invalid_binary_image(user, db):
    brand = Brand.objects.create(name="Form Brand")
    category = Category.objects.create(name="Form Category")
    bad_upload = SimpleUploadedFile("unsafe.jpg", b"this-is-not-an-image", content_type="image/jpeg")

    form = SellerProductCreateForm(
        data={
            "sku": "55667788",
            "name": "Protected Product",
            "brand": str(brand.id),
            "category": str(category.id),
            "price": "99.90",
            "stock_qty": "5",
        },
        files=MultiValueDict({"image_files": [bad_upload]}),
        user=user,
    )

    assert not form.is_valid()
    assert any("безопасное изображение" in error for error in form.non_field_errors())


def test_seller_product_import_form_rejects_non_csv_binary(db):
    upload = SimpleUploadedFile("catalog.csv", b"\xff\xd8\xffbroken", content_type="image/jpeg")
    form = SellerProductImportForm(files=MultiValueDict({"csv_file": [upload]}))

    assert not form.is_valid()
    assert "Неверный content-type" in form.errors["csv_file"][0]


def test_notification_preferences_and_ops_pages(client_logged, user, db):
    r0 = client_logged.post(
        "/account/preferences/",
        {
            "notify_email_orders": "on",
            "notify_telegram_orders": "on",
        },
    )
    assert r0.status_code in (302, 303)
    user.profile.refresh_from_db()
    assert user.profile.notify_email_orders is True

    r1 = client_logged.get("/account/notifications/")
    assert r1.status_code == 200

    profile = UserProfile.objects.get(user=user)
    profile.role = UserProfile.Role.SELLER
    profile.save(update_fields=["role"])
    le = LegalEntity.objects.create(name="Ops LE", inn="7707083811", bik="044525225", checking_account="40702810900000000091")
    LegalEntityMembership.objects.create(user=user, legal_entity=le)
    SellerStore.objects.create(owner=user, legal_entity=le, name="Ops Store", commission_rate="7.50")
    Product.objects.create(sku="88776655", name="Ops Product", price="20.00", stock_qty=2, seller=user)

    assert client_logged.get("/account/seller/analytics/").status_code == 200
    assert client_logged.get("/account/seller/payouts/").status_code == 200
    assert client_logged.get("/account/seller/warehouses/").status_code == 200
    assert client_logged.get("/account/seller/invoices/").status_code == 200
