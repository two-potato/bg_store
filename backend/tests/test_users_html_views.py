import pytest
import re
from django.core import mail
from rest_framework_simplejwt.tokens import AccessToken
from orders.models import Order
from commerce.models import LegalEntity, LegalEntityMembership, DeliveryAddress, LegalEntityCreationRequest, SellerStore
from users.models import UserProfile
from catalog.models import Brand, Category, Product, ProductReview, ProductReviewComment

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
    payload = AccessToken(token)
    assert payload["typ"] == "email_confirm"
    assert payload["uid"] == new_user.id
    assert payload["eml"] == "newuser@example.com"

    # cannot login before email confirmation
    r_pre = client.post("/account/login/", {"identifier": "newuser@example.com", "password": "p@ss12345"})
    assert r_pre.status_code == 200

    # confirm email via JWT link and get authenticated session
    r_confirm = client.get(f"/account/confirm-email/?token={token}")
    assert r_confirm.status_code in (302, 303)
    assert r_confirm.headers.get("Location", "").startswith("/account/")
    new_user.refresh_from_db()
    assert new_user.is_active is True
    assert "_auth_user_id" in client.session
    assert str(new_user.id) == client.session["_auth_user_id"]

    # logout
    r5 = client.get("/account/logout/")
    assert r5.status_code in (302, 303)


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
    from users import views_html as vhtml
    monkeypatch.setattr(vhtml, "verify_init_data", lambda _: {"id": 1, "username": "tg"})
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

    from users import views_html as vhtml
    monkeypatch.setattr(vhtml, "_verify_turnstile", lambda token, remoteip: (False, "captcha error"))

    blocked = client.post(
        "/account/login/",
        {"identifier": user.username, "password": "pass"},
    )
    assert blocked.status_code == 200
    assert "captcha error" in blocked.text
