import json
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from catalog.models import Brand, Category, Product, Series
from commerce.models import (
    DeliveryAddress,
    LegalEntity,
    LegalEntityCreationRequest,
    LegalEntityMembership,
    RequestStatus,
)
from orders.models import (
    FakeAcquiringPayment,
    Order,
    OrderClaim,
    OrderItem,
    OrderSupportTicket,
)
from orders.services import plan_seller_splits
from shopfront.models import FavoriteProduct, PersistentCart, SavedSearch
from users.models import UserProfile

pytestmark = pytest.mark.django_db


def _make_product(*, sku: str = "12345678", price: Decimal = Decimal("100.00"), stock_qty: int = 10) -> Product:
    brand = Brand.objects.create(name=f"Brand-{sku}")
    series = Series.objects.create(brand=brand, name=f"Series-{sku}")
    category = Category.objects.create(name=f"Category-{sku}")
    return Product.objects.create(
        sku=sku,
        name=f"Product-{sku}",
        brand=brand,
        series=series,
        category=category,
        price=price,
        stock_qty=stock_qty,
    )


def test_storefront_session_bootstrap_sets_csrf_for_guest(client):
    response = client.get("/api/storefront/session/bootstrap/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["session"]["authenticated"] is False
    assert isinstance(payload["session"]["csrf_token"], str)
    assert payload["session"]["csrf_token"] != ""
    assert "csrftoken" in response.cookies


def test_storefront_session_bootstrap_merges_persistent_cart_for_authenticated(client_logged, user):
    product = _make_product(sku="12345679", stock_qty=7)
    PersistentCart.objects.update_or_create(user=user, defaults={"payload": {str(product.id): {"qty": 3}}})

    response = client_logged.get("/api/storefront/session/bootstrap/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session"]["authenticated"] is True
    assert payload["cart_badge"]["count"] == 3
    assert client_logged.session["cart"][str(product.id)]["qty"] == 3


def test_storefront_cart_json_flow_add_update_remove_clear(client):
    product = _make_product(sku="12345680", price=Decimal("250.00"), stock_qty=3)

    add = client.post(
        "/api/storefront/cart/add/",
        data=json.dumps({"product_id": product.id, "qty": 10}),
        content_type="application/json",
    )
    assert add.status_code == 200
    add_payload = add.json()
    assert add_payload["ok"] is True
    assert add_payload["item"]["qty"] == 3
    assert add_payload["cart"]["cart_count"] == 3
    assert add_payload["cart"]["total"] == "750.00"

    update = client.post(
        "/api/storefront/cart/update/",
        data=json.dumps({"product_id": product.id, "op": "set", "qty": 2}),
        content_type="application/json",
    )
    assert update.status_code == 200
    update_payload = update.json()
    assert update_payload["item"]["qty"] == 2
    assert update_payload["cart"]["total"] == "500.00"

    get_cart = client.get("/api/storefront/cart/")
    assert get_cart.status_code == 200
    assert get_cart.json()["cart"]["items"][0]["product"]["id"] == product.id

    remove = client.post(
        "/api/storefront/cart/remove/",
        data=json.dumps({"product_id": product.id}),
        content_type="application/json",
    )
    assert remove.status_code == 200
    assert remove.json()["cart"]["cart_count"] == 0

    clear = client.post("/api/storefront/cart/clear/")
    assert clear.status_code == 200
    assert clear.json()["cart"]["is_empty"] is True


def test_storefront_account_bootstrap_requires_auth(client):
    response = client.get("/api/storefront/account/bootstrap/")

    assert response.status_code == 401
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "authentication_required"
    assert "login_url" in payload
    assert "next=%2Faccount%2F" in payload["login_url"]


def test_storefront_account_bootstrap_returns_summary(client_logged, user):
    legal_entity = LegalEntity.objects.create(
        name="LE Buyer",
        inn="7707083895",
        bik="044525225",
        checking_account="40702810900000000005",
    )
    LegalEntityMembership.objects.create(user=user, legal_entity=legal_entity)
    DeliveryAddress.objects.create(
        legal_entity=legal_entity,
        label="Main Office",
        country="RU",
        city="Moscow",
        street="Lenina 1",
        postcode="101000",
    )
    Order.objects.create(
        legal_entity=legal_entity,
        placed_by=user,
        status=Order.Status.NEW,
        approval_status=Order.ApprovalStatus.PENDING,
        payment_method=Order.PaymentMethod.INVOICE,
        subtotal=Decimal("1200.00"),
        discount_amount=Decimal("100.00"),
        total=Decimal("1100.00"),
    )

    response = client_logged.get("/api/storefront/account/bootstrap/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["metrics"]["orders_count"] == 1
    assert payload["metrics"]["entities_count"] == 1
    assert payload["metrics"]["addresses_count"] == 1
    assert len(payload["queues"]["recent_orders"]) == 1
    assert payload["queues"]["recent_orders"][0]["total"] == "1100.00"


def test_storefront_order_detail_requires_auth(client):
    response = client.get("/api/storefront/orders/1/")

    assert response.status_code == 401
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "authentication_required"
    assert "next=%2Faccount%2Forders%2F1%2F" in payload["login_url"]


def test_storefront_favorites_requires_auth_with_buyer_next(client):
    response = client.get("/api/storefront/tools/favorites/")

    assert response.status_code == 401
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "authentication_required"
    assert "next=%2Faccount%2Ffavorites%2F" in payload["login_url"]


def test_storefront_saved_lists_requires_auth_with_buyer_next(client):
    response = client.post("/api/storefront/tools/lists/42/add/")

    assert response.status_code == 401
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "authentication_required"
    assert "next=%2Faccount%2Flists%2F42%2F" in payload["login_url"]


def test_storefront_saved_searches_requires_auth_with_buyer_next(client):
    response = client.get("/api/storefront/tools/saved-searches/")

    assert response.status_code == 401
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"] == "authentication_required"
    assert "next=%2Faccount%2Fsaved-searches%2F" in payload["login_url"]


def test_storefront_order_detail_returns_tracking_payment_and_support_metadata(client_logged, user):
    seller = get_user_model().objects.create_user(username="bridge_seller", password="pass")
    product = _make_product(sku="12345681", price=Decimal("130.00"), stock_qty=9)
    product.seller = seller
    product.save(update_fields=["seller"])
    legal_entity = LegalEntity.objects.create(
        name="LE Detail",
        inn="7707083896",
        bik="044525225",
        checking_account="40702810900000000006",
    )
    order = Order.objects.create(
        legal_entity=legal_entity,
        placed_by=user,
        payment_method=Order.PaymentMethod.MIR_CARD,
        status=Order.Status.CONFIRMED,
        approval_status=Order.ApprovalStatus.PENDING,
        subtotal=Decimal("260.00"),
        discount_amount=Decimal("10.00"),
        total=Decimal("250.00"),
    )
    OrderItem.objects.create(
        order=order,
        product=product,
        seller_offer=None,
        name=product.name,
        price=Decimal("130.00"),
        qty=2,
    )
    plan_seller_splits(order)
    seller_order = order.seller_orders.first()
    shipment = seller_order.shipments.first()
    shipment.tracking_number = "TRACK-ORDER-1"
    shipment.delivery_method = "courier"
    shipment.warehouse_name = "WH-Bridge"
    shipment.status = shipment.Status.IN_TRANSIT
    shipment.save(update_fields=["tracking_number", "delivery_method", "warehouse_name", "status", "updated_at"])
    FakeAcquiringPayment.objects.create(
        order=order,
        amount=Decimal("250.00"),
        provider_payment_id=f"bridge_order_{order.id}",
        status=FakeAcquiringPayment.Status.PROCESSING,
        last_event=FakeAcquiringPayment.Event.START,
    )
    OrderClaim.objects.create(
        order=order,
        created_by=user,
        claim_type=OrderClaim.ClaimType.DELIVERY,
        status=OrderClaim.Status.OPEN,
        message="Где заказ?",
    )
    OrderSupportTicket.objects.create(
        order=order,
        created_by=user,
        topic=OrderSupportTicket.Topic.PAYMENT,
        status=OrderSupportTicket.Status.OPEN,
        subject="Проверить оплату",
        message="Платеж в обработке",
    )

    response = client_logged.get(f"/api/storefront/orders/{order.id}/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    order_payload = payload["order"]
    assert order_payload["id"] == order.id
    assert order_payload["tracking"]["available"] is True
    assert order_payload["tracking"]["shipments"][0]["tracking_number"] == "TRACK-ORDER-1"
    assert order_payload["payment"]["fake_payment"]["status"] == FakeAcquiringPayment.Status.PROCESSING
    assert order_payload["payment"]["can_retry"] is True
    assert order_payload["support"]["claims_count"] == 1
    assert order_payload["support"]["support_tickets_count"] == 1
    assert len(order_payload["timeline"]) == 9
    assert order_payload["timeline"][0]["key"] == "created"
    assert any(step["key"] == "claim_opened_or_resolved" and step["state"] == "issue" for step in order_payload["timeline"])
    assert order_payload["actions"]["can_reorder"] is True


def test_storefront_order_reorder_returns_partial_breakdown(client_logged, user):
    seller = get_user_model().objects.create_user(username="bridge_seller_reorder", password="pass")
    product_full = _make_product(sku="12345682", price=Decimal("100.00"), stock_qty=20)
    product_partial = _make_product(sku="12345683", price=Decimal("50.00"), stock_qty=3)
    product_none = _make_product(sku="12345684", price=Decimal("30.00"), stock_qty=2)
    for product in (product_full, product_partial, product_none):
        product.seller = seller
        product.save(update_fields=["seller"])

    order = Order.objects.create(
        placed_by=user,
        payment_method=Order.PaymentMethod.INVOICE,
        status=Order.Status.NEW,
        approval_status=Order.ApprovalStatus.NOT_REQUIRED,
    )
    OrderItem.objects.create(order=order, product=product_full, name=product_full.name, price=product_full.price, qty=2)
    OrderItem.objects.create(order=order, product=product_partial, name=product_partial.name, price=product_partial.price, qty=5)
    OrderItem.objects.create(order=order, product=product_none, name=product_none.name, price=product_none.price, qty=2)

    session = client_logged.session
    session["cart"] = {str(product_none.id): {"qty": 2}}
    session.save()

    response = client_logged.post(f"/api/storefront/orders/{order.id}/reorder/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    reorder_payload = payload["reorder"]
    assert reorder_payload["result_type"] == "partial"
    assert reorder_payload["summary"]["added_lines"] == 1
    assert reorder_payload["summary"]["adjusted_lines"] == 1
    assert reorder_payload["summary"]["unavailable_lines"] == 1
    assert any(row["product_id"] == product_full.id for row in reorder_payload["added"])
    assert any(row["product_id"] == product_partial.id for row in reorder_payload["adjusted"])
    assert any(row["product_id"] == product_none.id for row in reorder_payload["unavailable"])
    assert payload["cart"]["cart_count"] == 7


def test_storefront_account_settings_get_and_post(client_logged, user):
    response = client_logged.get("/api/storefront/account/settings/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["settings"]["username"] == user.username

    update = client_logged.post(
        "/api/storefront/account/settings/",
        data=json.dumps(
            {
                "full_name": "Buyer One",
                "contact_email": "buyer.one@example.com",
                "phone": "+79990001122",
            }
        ),
        content_type="application/json",
    )
    assert update.status_code == 200
    user.refresh_from_db()
    profile = UserProfile.objects.get(user=user)
    assert profile.full_name == "Buyer One"
    assert profile.contact_email == "buyer.one@example.com"
    assert profile.phone == "+79990001122"
    assert user.email == "buyer.one@example.com"


def test_storefront_account_preferences_get_and_post(client_logged, user):
    response = client_logged.get("/api/storefront/account/preferences/")
    assert response.status_code == 200
    assert response.json()["ok"] is True

    update = client_logged.post(
        "/api/storefront/account/preferences/",
        data=json.dumps(
            {
                "notify_email_orders": False,
                "notify_email_marketing": True,
                "notify_telegram_orders": False,
                "notify_telegram_marketing": True,
            }
        ),
        content_type="application/json",
    )
    assert update.status_code == 200
    profile = UserProfile.objects.get(user=user)
    assert profile.notify_email_orders is False
    assert profile.notify_email_marketing is True
    assert profile.notify_telegram_orders is False
    assert profile.notify_telegram_marketing is True


def test_storefront_account_addresses_list_create_default_delete(client_logged, user):
    legal_entity = LegalEntity.objects.create(
        name="LE Address",
        inn="7707083897",
        bik="044525225",
        checking_account="40702810900000000007",
    )
    LegalEntityMembership.objects.create(user=user, legal_entity=legal_entity)

    listing = client_logged.get("/api/storefront/account/addresses/")
    assert listing.status_code == 200
    assert listing.json()["addresses"] == []

    created = client_logged.post(
        "/api/storefront/account/addresses/",
        data=json.dumps(
            {
                "legal_entity": legal_entity.id,
                "label": "HQ",
                "country": "RU",
                "city": "Moscow",
                "street": "Lenina 10",
                "postcode": "101000",
                "is_default": True,
            }
        ),
        content_type="application/json",
    )
    assert created.status_code == 200
    address_id = created.json()["address"]["id"]

    another = client_logged.post(
        "/api/storefront/account/addresses/",
        data=json.dumps(
            {
                "legal_entity": legal_entity.id,
                "label": "WH",
                "country": "RU",
                "city": "Moscow",
                "street": "Skladskaya 1",
                "postcode": "101001",
                "is_default": False,
            }
        ),
        content_type="application/json",
    )
    assert another.status_code == 200
    second_id = another.json()["address"]["id"]

    set_default = client_logged.post(f"/api/storefront/account/addresses/{second_id}/default/")
    assert set_default.status_code == 200
    first_address = DeliveryAddress.objects.get(id=address_id)
    second_address = DeliveryAddress.objects.get(id=second_id)
    assert first_address.is_default is False
    assert second_address.is_default is True

    deleted = client_logged.post(f"/api/storefront/account/addresses/{address_id}/delete/")
    assert deleted.status_code == 200
    assert DeliveryAddress.objects.filter(id=address_id).exists() is False


def test_storefront_account_legal_entities_and_notifications(client_logged, user):
    pending_status, _ = RequestStatus.objects.get_or_create(code="pending", defaults={"name": "На рассмотрении"})
    legal_entity = LegalEntity.objects.create(
        name="LE Legal",
        inn="7707083898",
        bik="044525225",
        checking_account="40702810900000000008",
    )
    LegalEntityMembership.objects.create(user=user, legal_entity=legal_entity)
    LegalEntityCreationRequest.objects.create(
        applicant=user,
        name="New Buyer LE",
        inn="7707083899",
        bik="044525225",
        checking_account="40702810900000000009",
        bank_name="Test Bank",
        status=pending_status,
    )
    Order.objects.create(
        legal_entity=legal_entity,
        placed_by=user,
        status=Order.Status.NEW,
        approval_status=Order.ApprovalStatus.PENDING,
        payment_method=Order.PaymentMethod.INVOICE,
        subtotal=Decimal("100.00"),
        discount_amount=Decimal("0.00"),
        total=Decimal("100.00"),
    )

    legal_response = client_logged.get("/api/storefront/account/legal-entities/")
    assert legal_response.status_code == 200
    legal_payload = legal_response.json()
    assert legal_payload["ok"] is True
    assert len(legal_payload["memberships"]) == 1
    assert len(legal_payload["company_workspaces"]) == 1
    assert len(legal_payload["creation_requests"]) == 1

    notifications_response = client_logged.get("/api/storefront/account/notifications/")
    assert notifications_response.status_code == 200
    notifications_payload = notifications_response.json()
    assert notifications_payload["ok"] is True
    assert len(notifications_payload["notifications"]) >= 1


def test_storefront_favorites_list_and_toggle(client_logged, user):
    product = _make_product(sku="12345685", price=Decimal("90.00"), stock_qty=12)
    FavoriteProduct.objects.create(user=user, product=product)

    listing = client_logged.get("/api/storefront/tools/favorites/")
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["ok"] is True
    assert len(payload["favorites"]) == 1
    assert payload["favorites"][0]["id"] == product.id

    remove = client_logged.post(
        "/api/storefront/tools/favorites/toggle/",
        data=json.dumps({"product_id": product.id}),
        content_type="application/json",
    )
    assert remove.status_code == 200
    assert remove.json()["favorited"] is False

    add = client_logged.post(
        "/api/storefront/tools/favorites/toggle/",
        data=json.dumps({"product_id": product.id}),
        content_type="application/json",
    )
    assert add.status_code == 200
    assert add.json()["favorited"] is True


def test_storefront_saved_lists_flow_create_add_remove_move_toggle_delete(client_logged):
    product = _make_product(sku="12345686", price=Decimal("145.00"), stock_qty=10)

    created = client_logged.post(
        "/api/storefront/tools/lists/",
        data=json.dumps({"name": "Команда закупок", "description": "Q2 list"}),
        content_type="application/json",
    )
    assert created.status_code == 200
    list_id = created.json()["saved_list"]["id"]

    add_item = client_logged.post(
        f"/api/storefront/tools/lists/{list_id}/add/",
        data=json.dumps({"product_id": product.id, "qty": 3}),
        content_type="application/json",
    )
    assert add_item.status_code == 200
    item_id = add_item.json()["item"]["id"]
    assert add_item.json()["item"]["quantity"] == 3

    detail = client_logged.get(f"/api/storefront/tools/lists/{list_id}/")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["ok"] is True
    assert detail_payload["saved_list"]["id"] == list_id
    assert len(detail_payload["saved_list"]["items"]) == 1

    moved = client_logged.post(f"/api/storefront/tools/lists/{list_id}/move-to-cart/")
    assert moved.status_code == 200
    assert moved.json()["ok"] is True
    assert moved.json()["moved_items"] == 1
    assert moved.json()["cart"]["cart_count"] == 3

    toggled = client_logged.post(f"/api/storefront/tools/lists/{list_id}/toggle-public/")
    assert toggled.status_code == 200
    assert toggled.json()["is_public"] is True
    assert toggled.json()["share_token"] != ""

    removed = client_logged.post(
        f"/api/storefront/tools/lists/{list_id}/remove-item/",
        data=json.dumps({"item_id": item_id}),
        content_type="application/json",
    )
    assert removed.status_code == 200
    assert removed.json()["ok"] is True

    deleted = client_logged.post(f"/api/storefront/tools/lists/{list_id}/delete/")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True


def test_storefront_saved_searches_list_create_delete(client_logged, user):
    SavedSearch.objects.create(user=user, name="Электроника", querystring="q=tv&brand=sony")

    listing = client_logged.get("/api/storefront/tools/saved-searches/")
    assert listing.status_code == 200
    listing_payload = listing.json()
    assert listing_payload["ok"] is True
    assert len(listing_payload["saved_searches"]) == 1

    created = client_logged.post(
        "/api/storefront/tools/saved-searches/",
        data=json.dumps({"name": "Мониторы", "querystring": "q=monitor&stock=instock"}),
        content_type="application/json",
    )
    assert created.status_code == 200
    search_id = created.json()["saved_search"]["id"]

    deleted = client_logged.post(f"/api/storefront/tools/saved-searches/{search_id}/delete/")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True
    assert SavedSearch.objects.filter(id=search_id).exists() is False


def test_storefront_wave_analytics_ingest_accepts_allowed_event(client_logged):
    response = client_logged.post(
        "/api/storefront/analytics/ingest/",
        data=json.dumps({"event": "order_detail_viewed", "surface": "next_order_detail"}),
        content_type="application/json",
    )
    assert response.status_code == 204


def test_storefront_wave_analytics_ingest_rejects_unsupported_event(client_logged):
    response = client_logged.post(
        "/api/storefront/analytics/ingest/",
        data=json.dumps({"event": "totally_unknown_event"}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "unsupported_event"
