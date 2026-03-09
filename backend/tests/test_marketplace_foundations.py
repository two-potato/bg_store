import pytest
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory

from catalog.models import Brand, Category, Product, SellerOffer, SellerInventory
from commerce.models import LegalEntity, SellerStore
from orders.models import Order, OrderItem, SellerOrder, Shipment
from orders.services import plan_seller_splits
from shopfront.catalog_selectors import category_descendant_ids, category_option_rows
from shopfront.cart_checkout_service import cart_badge_context, cart_summary
from shopfront.checkout_flow_service import ensure_checkout_idempotency_key
from shopfront.cart_store import merge_session_cart_with_persistent
from shopfront.models import PersistentCart
from catalog.offer_service import apply_offer_snapshot


pytestmark = pytest.mark.django_db


def test_merge_session_cart_with_persistent_uses_max_qty():
    User = get_user_model()
    user = User.objects.create_user(username="merge_user", password="pass")
    PersistentCart.objects.create(user=user, payload={"10": {"qty": 2}, "11": {"qty": 1}})

    merged = merge_session_cart_with_persistent(user, {"10": {"qty": 5}, "12": {"qty": 3}})

    assert merged == {"10": {"qty": 5}, "11": {"qty": 1}, "12": {"qty": 3}}


def test_plan_seller_splits_creates_snapshot_rows():
    User = get_user_model()
    seller = User.objects.create_user(username="seller_split", password="pass")
    customer = User.objects.create_user(username="buyer_split", password="pass")
    brand = Brand.objects.create(name="SplitBrand")
    category = Category.objects.create(name="SplitCategory")
    legal_entity = LegalEntity.objects.create(name="Split LE", inn="7707083891", bik="044525225", checking_account="40702810900000001009")
    SellerStore.objects.create(owner=seller, legal_entity=legal_entity, name="Split Store")
    product = Product.objects.create(sku="12341234", name="Split Product", brand=brand, category=category, price=120, stock_qty=5, seller=seller)
    offer = SellerOffer.objects.create(product=product, seller=seller, seller_store=seller.seller_store, price=99, min_order_qty=2)
    SellerInventory.objects.create(offer=offer, warehouse_name="Main", stock_qty=12, reserved_qty=1, is_primary=True, eta_days=1)
    order = Order.objects.create(placed_by=customer, payment_method=Order.PaymentMethod.CASH)
    OrderItem.objects.create(order=order, product=product, seller_offer=offer, name=product.name, price=offer.price, qty=2)

    splits = plan_seller_splits(order)

    assert len(splits) == 1
    assert splits[0].seller == seller
    assert splits[0].items_count == 2
    assert str(splits[0].subtotal) == "198.00"
    assert SellerOrder.objects.filter(order=order, seller=seller).exists()
    assert Shipment.objects.filter(seller_order__order=order).exists()


def test_apply_offer_snapshot_prefers_active_offer_inventory():
    User = get_user_model()
    seller = User.objects.create_user(username="offer_seller", password="pass")
    brand = Brand.objects.create(name="OfferBrand")
    category = Category.objects.create(name="OfferCategory")
    legal_entity = LegalEntity.objects.create(name="Offer LE", inn="7707083892", bik="044525225", checking_account="40702810900000001010")
    store = SellerStore.objects.create(owner=seller, legal_entity=legal_entity, name="Offer Store")
    product = Product.objects.create(sku="55556666", name="Offer Product", brand=brand, category=category, price=150, stock_qty=1, seller=seller)
    offer = SellerOffer.objects.create(product=product, seller=seller, seller_store=store, price=120, min_order_qty=3, lead_time_days=4)
    SellerInventory.objects.create(offer=offer, warehouse_name="A", stock_qty=20, reserved_qty=5, is_primary=True, eta_days=2)

    apply_offer_snapshot([product])

    assert str(product.display_price) == "120.00"
    assert product.display_stock_qty == 15
    assert product.display_min_order_qty == 3
    assert product.display_lead_time_days == 2


def test_category_descendant_ids_returns_nested_tree():
    root = Category.objects.create(name="Root Tree", slug="root-tree")
    child = Category.objects.create(name="Child Tree", slug="child-tree", parent=root)
    grand = Category.objects.create(name="Grand Tree", slug="grand-tree", parent=child)

    ids = category_descendant_ids(root)

    assert ids == [root.id, child.id, grand.id]


def test_category_option_rows_marks_depth():
    root = Category.objects.create(name="Depth Root", slug="depth-root")
    child = Category.objects.create(name="Depth Child", slug="depth-child", parent=root)

    rows = category_option_rows([root, child])

    assert rows[0]["name"] == "Depth Root"
    assert rows[0]["depth"] == 0
    assert rows[1]["name"] == "Depth Child"
    assert rows[1]["depth"] == 1


def test_cart_summary_uses_offer_price_and_groups_by_seller():
    factory = RequestFactory()
    request = factory.get("/cart/")
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()
    request.user = type("Anon", (), {"is_authenticated": False})()

    seller = get_user_model().objects.create_user(username="cart_seller", password="pass")
    brand = Brand.objects.create(name="Cart Brand")
    category = Category.objects.create(name="Cart Category")
    legal_entity = LegalEntity.objects.create(name="Cart LE", inn="7707083894", bik="044525225", checking_account="40702810900000001011")
    store = SellerStore.objects.create(owner=seller, legal_entity=legal_entity, name="Cart Store")
    product = Product.objects.create(sku="90001111", name="Cart Product", brand=brand, category=category, price=250, stock_qty=2, seller=seller)
    offer = SellerOffer.objects.create(product=product, seller=seller, seller_store=store, price=190, min_order_qty=2)
    SellerInventory.objects.create(offer=offer, warehouse_name="Cart WH", stock_qty=9, reserved_qty=1, is_primary=True, eta_days=3)
    request.session["cart"] = {str(product.id): {"qty": 2}}

    summary = cart_summary(request)

    assert str(summary["subtotal"]) == "380.00"
    assert summary["seller_count"] == 1
    assert summary["cart_count"] == 2
    assert summary["seller_groups"][0]["title"] == "Cart Store"
    assert cart_badge_context(request)["count"] == 2


def test_ensure_checkout_idempotency_key_persists_between_calls():
    factory = RequestFactory()
    request = factory.get("/checkout/")
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()

    generated = []

    def _key_factory():
        generated.append("generated-key")
        return "generated-key"

    first = ensure_checkout_idempotency_key(request, _key_factory)
    second = ensure_checkout_idempotency_key(request, _key_factory)

    assert first == "generated-key"
    assert second == "generated-key"
    assert generated == ["generated-key"]
