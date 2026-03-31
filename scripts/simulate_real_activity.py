# ruff: noqa: E402
#!/usr/bin/env python3
import os
import random
import sys
from dataclasses import dataclass
from decimal import Decimal


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from django.test.utils import override_settings

from catalog.models import Brand, Category, Product
from commerce.models import LegalEntity, LegalEntityMembership, SellerStore
from orders.models import Order
from users.models import UserProfile


User = get_user_model()
PASSWORD = "Passw0rd!123"
RNG = random.Random(20260311)


@dataclass
class ScenarioResult:
    sellers_created: int = 0
    buyers_created: int = 0
    guest_orders: int = 0
    buyer_orders: int = 0
    pages_loaded: int = 0
    cart_adds: int = 0


def _unique_digits(length: int, seed: int) -> str:
    raw = str(seed).zfill(length)
    return raw[-length:]


def ensure_seller(index: int):
    username = f"scenario-seller-{index}"
    email = f"{username}@example.com"
    user, created = User.objects.get_or_create(
        username=username,
        defaults={"email": email, "is_active": True},
    )
    if created:
        user.set_password(PASSWORD)
        user.save(update_fields=["password"])
    profile = user.profile
    profile.role = UserProfile.Role.SELLER
    profile.full_name = f"Scenario Seller {index}"
    profile.contact_email = email
    profile.phone = f"+79990000{index:03d}"
    profile.save(update_fields=["role", "full_name", "contact_email", "phone"])

    legal_entity, _ = LegalEntity.objects.get_or_create(
        inn=f"77{index:010d}"[:12],
        defaults={
            "name": f"Scenario Seller Entity {index}",
            "bik": "044525225",
            "checking_account": f"40702810{index:012d}"[:20],
            "bank_name": "Scenario Bank",
        },
    )
    if legal_entity.name != f"Scenario Seller Entity {index}":
        legal_entity.name = f"Scenario Seller Entity {index}"
        legal_entity.save(update_fields=["name"])

    LegalEntityMembership.objects.get_or_create(user=user, legal_entity=legal_entity)
    store, _ = SellerStore.objects.get_or_create(
        owner=user,
        defaults={
            "legal_entity": legal_entity,
            "name": f"Scenario Store {index}",
            "description": "Scenario-generated seller storefront",
            "moderation_status": SellerStore.ModerationStatus.APPROVED,
        },
    )
    if store.moderation_status != SellerStore.ModerationStatus.APPROVED:
        store.moderation_status = SellerStore.ModerationStatus.APPROVED
        store.save(update_fields=["moderation_status"])
    return user, created


def ensure_products_for_seller(seller, start_index: int, count: int = 3) -> list[Product]:
    category, _ = Category.objects.get_or_create(name="Scenario Category", slug="scenario-category")
    brand, _ = Brand.objects.get_or_create(name=f"Scenario Brand {seller.id}")
    products: list[Product] = []
    for offset in range(count):
        idx = start_index + offset
        sku = f"SC{idx:06d}"[:8]
        product, _ = Product.objects.get_or_create(
            sku=sku,
            defaults={
                "name": f"Scenario Product {idx}",
                "brand": brand,
                "category": category,
                "seller": seller,
                "price": Decimal("149.00") + Decimal(offset * 10),
                "stock_qty": 50,
                "is_new": True,
            },
        )
        if product.seller_id != seller.id:
            product.seller = seller
            product.save(update_fields=["seller"])
        products.append(product)
    return products


def ensure_buyer(index: int):
    username = f"scenario-buyer-{index}"
    email = f"{username}@example.com"
    user, created = User.objects.get_or_create(
        username=username,
        defaults={"email": email, "is_active": True},
    )
    if created:
        user.set_password(PASSWORD)
        user.save(update_fields=["password"])
    profile = user.profile
    profile.full_name = f"Scenario Buyer {index}"
    profile.contact_email = email
    profile.phone = f"+78880000{index:03d}"
    profile.save(update_fields=["full_name", "contact_email", "phone"])
    return user, created


def _assert_ok(response, expected_statuses=(200, 302, 303)):
    if response.status_code not in expected_statuses:
        raise RuntimeError(f"Unexpected status {response.status_code} for {response.request.get('PATH_INFO')}")


def guest_checkout(product: Product, result: ScenarioResult, index: int):
    with override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"]):
        client = Client(HTTP_HOST="localhost")
        for path in ("/", "/catalog/", f"/product/{product.slug}/", "/cart/", "/checkout/"):
            response = client.get(path)
            _assert_ok(response, (200,))
            result.pages_loaded += 1
        add = client.post("/cart/add/", {"product_id": product.id, "qty": 1}, HTTP_HX_REQUEST="true")
        _assert_ok(add, (200,))
        result.cart_adds += 1
        checkout = client.post(
            "/checkout/submit/",
            {
                "customer_type": "individual",
                "payment_method": "cash",
                "delivery_method": "courier",
                "customer_name": f"Guest Buyer {index}",
                "customer_email": f"guest-checkout-{index}@example.com",
                "customer_phone": f"+7999555{index:04d}"[:12],
                "address_text": "Moscow, Scenario street, 1",
            },
            HTTP_HX_REQUEST="true",
        )
        _assert_ok(checkout, (200,))
        result.guest_orders += 1


def buyer_checkout(buyer, products: list[Product], result: ScenarioResult, index: int):
    with override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"]):
        client = Client(HTTP_HOST="localhost")
        client.force_login(buyer)
        for product in products[:2]:
            response = client.get(f"/product/{product.slug}/")
            _assert_ok(response, (200,))
            result.pages_loaded += 1
            toggle = client.post("/favorites/toggle/", {"product_id": product.id}, HTTP_HX_REQUEST="true")
            _assert_ok(toggle, (200,))
            compare = client.post("/compare/toggle/", {"product_id": product.id}, HTTP_HX_REQUEST="true")
            _assert_ok(compare, (200,))
            add = client.post("/cart/add/", {"product_id": product.id, "qty": 1}, HTTP_HX_REQUEST="true")
            _assert_ok(add, (200,))
            result.cart_adds += 1
        checkout = client.post(
            "/checkout/submit/",
            {
                "customer_type": "individual",
                "payment_method": "cash",
                "delivery_method": "courier",
                "customer_name": buyer.profile.full_name or buyer.username,
                "customer_email": buyer.email,
                "customer_phone": buyer.profile.phone or f"+7999111{index:04d}"[:12],
                "address_text": "Saint Petersburg, Scenario avenue, 5",
            },
            HTTP_HX_REQUEST="true",
        )
        _assert_ok(checkout, (200,))
        result.buyer_orders += 1


def main():
    result = ScenarioResult()

    seller_products: list[Product] = []
    for seller_index in range(1, 4):
        seller, created = ensure_seller(seller_index)
        if created:
            result.sellers_created += 1
        seller_products.extend(ensure_products_for_seller(seller, seller_index * 10))

    if not seller_products:
        raise RuntimeError("No scenario products available")

    for buyer_index in range(1, 6):
        buyer, created = ensure_buyer(buyer_index)
        if created:
            result.buyers_created += 1
        selected = RNG.sample(seller_products, k=min(3, len(seller_products)))
        buyer_checkout(buyer, selected, result, buyer_index)

    for guest_index, product in enumerate(RNG.sample(seller_products, k=min(4, len(seller_products))), start=1):
        guest_checkout(product, result, guest_index)

    total_scenario_orders = Order.objects.filter(customer_email__icontains="scenario-").count()
    print("scenario_summary", result)
    print("scenario_orders_total", total_scenario_orders)


if __name__ == "__main__":
    main()
