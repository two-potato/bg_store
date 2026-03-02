import pytest
from orders.models import Order
from commerce.models import LegalEntity, LegalEntityMembership, DeliveryAddress, LegalEntityCreationRequest
from users.models import UserProfile
from catalog.models import Product, ProductReview, ProductReviewComment

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


def test_login_register_logout(client, user):
    # login GET
    r0 = client.get("/account/login/")
    assert r0.status_code == 200
    # invalid credentials
    r1 = client.post("/account/login/", {"identifier": user.username, "password": "bad"})
    assert r1.status_code == 200
    # valid
    r2 = client.post("/account/login/", {"identifier": user.username, "password": "pass"})
    assert r2.status_code in (302, 303)
    # register
    r3 = client.get("/account/register/")
    assert r3.status_code in (200, 302, 303)
    r4 = client.post("/account/register/", {
        "username": "newuser",
        "email": "n@e.com",
        "password1": "p@ss12345",
        "password2": "p@ss12345",
    })
    assert r4.status_code in (302, 303)
    # logout
    r5 = client.get("/account/logout/")
    assert r5.status_code in (302, 303)


def test_login_page_google_button_state(client, settings):
    settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]["client_id"] = ""
    r_disabled = client.get("/account/login/")
    assert r_disabled.status_code == 200
    assert "Войти через Google (не настроено)" in r_disabled.text

    settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]["client_id"] = "client-id"
    r_enabled = client.get("/account/login/")
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
