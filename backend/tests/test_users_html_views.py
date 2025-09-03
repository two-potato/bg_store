import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from orders.models import Order
from commerce.models import LegalEntity, LegalEntityMembership, DeliveryAddress, LegalEntityCreationRequest

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
    r2 = client.post("/account/", {"email": "new@example.com", "first_name": "A", "last_name": "B"})
    assert r2.status_code in (302, 303)


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
    o = Order.objects.create(legal_entity=le, placed_by=user, delivery_address=addr)
    r = client_logged.get("/account/orders/")
    assert r.status_code == 200


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


def test_twa_login_flow(monkeypatch, client):
    # no initData -> redirect with message
    r0 = client.get("/account/twa/login/")
    assert r0.status_code in (302, 303)
    # valid flow
    from users import views_html as vhtml
    monkeypatch.setattr(vhtml, "verify_init_data", lambda _: {"id": 1, "username": "tg"})
    r1 = client.get("/account/twa/login/?initData=dummy")
    assert r1.status_code in (302, 303)
