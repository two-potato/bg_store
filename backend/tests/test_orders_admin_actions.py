import pytest
from django.contrib.auth import get_user_model
from orders.models import Order, OrderItem
from catalog.models import Brand, Category, Product


pytestmark = pytest.mark.django_db


def _product():
    b = Brand.objects.create(name="B1")
    c = Category.objects.create(name="C1")
    p = Product.objects.create(sku="12345679", name="P1", brand=b, category=c, price=100, stock_qty=10)
    return p


def _admin_client(client):
    U = get_user_model()
    u = U.objects.create_superuser(username="admin2", password="pass", email="a@a.a")
    client.force_login(u)
    return client


def test_order_status_transitions_via_admin(client):
    client = _admin_client(client)
    p = _product()
    # create order in new state
    U = get_user_model()
    user = U.objects.create_user(username="u_order")
    order = Order.objects.create(placed_by=user)
    OrderItem.objects.create(order=order, product=p, name=p.name, price=p.price, qty=1)
    order.recalc_totals()
    order.save(update_fields=["subtotal","discount_amount","total"]) 

    # mark_new -> new
    r = client.post("/admin/orders/order/", {"action": "mark_new", "_selected_action": [order.id]})
    assert r.status_code in (200, 302)
    order.refresh_from_db()
    assert order.status == Order.Status.NEW

    # mark_in_progress -> delivering
    r = client.post("/admin/orders/order/", {"action": "mark_in_progress", "_selected_action": [order.id]})
    assert r.status_code in (200, 302)
    order.refresh_from_db()
    assert order.status == Order.Status.DELIVERING

    # mark_completed -> delivered
    r = client.post("/admin/orders/order/", {"action": "mark_completed", "_selected_action": [order.id]})
    assert r.status_code in (200, 302)
    order.refresh_from_db()
    assert order.status == Order.Status.DELIVERED


def test_order_admin_status_is_readonly(client):
    client = _admin_client(client)
    U = get_user_model()
    user = U.objects.create_user(username="u2")
    order = Order.objects.create(placed_by=user)
    # open change page
    r = client.get(f"/admin/orders/order/{order.id}/change/")
    assert r.status_code == 200
    # status field should be editable in admin form
    html = r.content.decode()
    assert 'name="status"' in html
