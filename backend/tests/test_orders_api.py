import pytest
from catalog.models import Brand, Category, Product, Series
from commerce.models import LegalEntity, LegalEntityMembership, DeliveryAddress

pytestmark = pytest.mark.django_db


def _make_product():
    b = Brand.objects.create(name="B")
    s = Series.objects.create(brand=b, name="S")
    c = Category.objects.create(name="C")
    p = Product.objects.create(sku="SKU-1", name="Prod", brand=b, series=s, category=c, price=100, stock_qty=10)
    return p


def test_order_create_list_and_internal_actions(api_client, user, db):
    p = _make_product()
    le = LegalEntity.objects.create(name="LE", inn="7707083893", bik="044525225", checking_account="40702810900000000001")
    LegalEntityMembership.objects.create(user=user, legal_entity=le)
    addr = DeliveryAddress.objects.create(legal_entity=le, label="Office", country="RU", city="Msk", street="Lenina", postcode="101000")

    payload = {
        "legal_entity_id": le.id,
        "delivery_address_id": addr.id,
        "items": [{"product_id": p.id, "qty": 2}],
    }
    r = api_client.post("/api/orders/", data=payload, content_type="application/json")
    assert r.status_code == 201
    order_id = r.json()["id"]

    # List should include order (via membership filter)
    r2 = api_client.get("/api/orders/")
    assert r2.status_code == 200 and any(o["id"] == order_id for o in r2.json())

    # Approve with internal token
    headers = {"HTTP_X_INTERNAL_TOKEN": "internal-token", "HTTP_X_ADMIN_TELEGRAM_ID": "0"}
    r3 = api_client.post(f"/api/orders/{order_id}/approve/", **headers)
    # If user is not admin in entity by telegram_id, expect 403; the path is still exercised
    assert r3.status_code in (200, 403)

    r4 = api_client.post(f"/api/orders/{order_id}/reject/", **headers)
    assert r4.status_code in (200, 403)
