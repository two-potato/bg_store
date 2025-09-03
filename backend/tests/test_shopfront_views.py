import pytest
from catalog.models import Brand, Category, Product, Series, Tag
from commerce.models import LegalEntity, LegalEntityMembership, DeliveryAddress

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
    r2 = client.get(f"/catalog/?brand={b.id}&category={c.id}&q=P&tag={t.slug}")
    assert r2.status_code == 200


def test_product_page(client, db):
    p, *_ = _prod()
    r = client.get(f"/product/{p.id}/")
    assert r.status_code == 200


def test_cart_flow(client, db):
    p, *_ = _prod()
    # badge/panel empty
    assert client.get("/cart/badge/").status_code == 200
    assert client.get("/cart/panel/").status_code == 200
    # add
    r_add = client.post("/cart/add/", {"product_id": p.id, "qty": 2})
    assert r_add.status_code == 201
    # update inc
    r_u1 = client.post("/cart/update/", {"product_id": p.id, "op": "inc"})
    assert r_u1.status_code == 200
    # update set
    r_u2 = client.post("/cart/update/", {"product_id": p.id, "op": "set", "qty": 5})
    assert r_u2.status_code == 200
    # remove
    r_rm = client.post("/cart/remove/", {"product_id": str(p.id)})
    assert r_rm.status_code == 200
    # update for non-existing item -> 404 branch
    r_u3 = client.post("/cart/update/", {"product_id": p.id, "op": "inc"})
    assert r_u3.status_code == 404
    # clear
    r_cl = client.post("/cart/clear/")
    assert r_cl.status_code == 200


def test_checkout_company_and_individual(client_logged, user, db):
    p, *_ = _prod()
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
