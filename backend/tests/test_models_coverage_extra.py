import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from catalog.models import Brand, Category, Color, Country, Product, Series, Tag
from commerce.models import (
    DeliveryAddress,
    LegalEntity,
    LegalEntityCreationRequest,
    LegalEntityMembership,
    MembershipRole,
    RequestStatus,
)
from commerce.signals import ensure_entity_and_membership_on_approval
from core.middleware import RequestContextMiddleware
from orders.models import Order, OrderItem
from users.models import UserProfile

pytestmark = pytest.mark.django_db


def test_catalog_str_methods_cover_reference_models():
    color = Color.objects.create(name="Black", hex_code="#000000")
    country = Country.objects.create(name="Russia", iso_code="RUS")
    brand = Brand.objects.create(name="BrandX")
    series = Series.objects.create(brand=brand, name="S-1")
    category = Category.objects.create(name="CategoryX")
    tag = Tag.objects.create(name="Promo", slug="promo")
    product = Product.objects.create(
        sku="12344321",
        name="Cup",
        brand=brand,
        category=category,
        color=color,
        country_of_origin=country,
    )
    product.tags.add(tag)

    assert str(color) == "Black"
    assert str(country) == "Russia"
    assert str(series) == "BrandX / S-1"
    assert str(category) == "CategoryX"
    assert str(tag) == "Promo"
    assert str(product) == "12344321 — Cup"


def test_commerce_str_methods_and_default_role_assignment(user):
    le = LegalEntity.objects.create(
        name="Acme",
        inn="5408131553",
        bik="044525225",
        checking_account="40702810900000000003",
    )
    assert str(le) == "Acme (ИНН 5408131553)"

    # Fallback branch for __str__ when object has no name/inn.
    le_fallback = LegalEntity(name="", inn="", bik="", checking_account="")
    le_fallback.pk = 42
    assert str(le_fallback) == "Юрлицо #42"

    role, _ = MembershipRole.objects.get_or_create(code="owner", defaults={"name": "Owner"})
    assert str(role) == role.name

    membership = LegalEntityMembership.objects.create(user=user, legal_entity=le)
    assert membership.role.code == "manager"
    assert "Менеджер" in str(membership)

    status, _ = RequestStatus.objects.get_or_create(code="approved", defaults={"name": "Approved"})
    assert str(status) == status.name

    addr1 = DeliveryAddress.objects.create(
        legal_entity=le,
        label="Main",
        country="RU",
        city="Moscow",
        street="Tverskaya, 1",
        postcode="101000",
        is_default=True,
    )
    addr2 = DeliveryAddress.objects.create(
        legal_entity=le,
        label="Warehouse",
        country="RU",
        city="Moscow",
        street="Leningradskaya, 10",
        postcode="101001",
        is_default=True,
    )
    addr1.refresh_from_db()
    assert addr1.is_default is False
    assert str(addr2) == "Warehouse — Moscow, Leningradskaya, 10"

    req = LegalEntityCreationRequest(
        applicant=user,
        name="Req LE",
        inn="7707083893",
        bik="044525225",
        checking_account="40702810900000000001",
        status=status,
    )
    # Explicitly covers no-op clean method branch.
    req.clean()


def test_signal_creates_entity_and_membership_when_approved(user):
    approved, _ = RequestStatus.objects.get_or_create(code="approved", defaults={"name": "Approved"})
    req = LegalEntityCreationRequest.objects.create(
        applicant=user,
        name="Signal LE",
        inn="7736207543",
        bik="044525225",
        checking_account="40702810900000000002",
        status=approved,
    )

    # Explicit call is idempotent and covers the creation branch in receiver.
    ensure_entity_and_membership_on_approval(
        sender=LegalEntityCreationRequest,
        instance=req,
        created=False,
    )

    le = LegalEntity.objects.get(inn="7736207543")
    membership = LegalEntityMembership.objects.get(user=user, legal_entity=le)
    assert membership.role.code == "owner"


def test_request_context_middleware_handles_non_mapping_response():
    class NoHeaderResponse:
        pass

    rf = RequestFactory()
    request = rf.get("/health/")
    middleware = RequestContextMiddleware(lambda _req: NoHeaderResponse())
    response = middleware(request)
    assert isinstance(response, NoHeaderResponse)


def test_user_profile_str():
    User = get_user_model()
    u = User.objects.create_user(username="profile_user", password="pass")
    profile = UserProfile.objects.get(user=u)
    assert str(profile) == "profile_user profile"


def test_order_recalc_totals_uses_profile_discount(user):
    user.profile.discount = 12.5
    user.profile.save(update_fields=["discount"])

    brand = Brand.objects.create(name="BrandD")
    category = Category.objects.create(name="CategoryD")
    product = Product.objects.create(
        sku="SKUD001",
        name="Discounted",
        brand=brand,
        category=category,
        price=200,
    )
    le = LegalEntity.objects.create(
        name="Disc LE",
        inn="6670524080",
        bik="044525225",
        checking_account="40702810900000000005",
    )
    addr = DeliveryAddress.objects.create(
        legal_entity=le,
        label="Main",
        country="RU",
        city="Moscow",
        street="Arbat, 1",
        postcode="101000",
    )
    order = Order.objects.create(legal_entity=le, placed_by=user, delivery_address=addr)
    OrderItem.objects.create(order=order, product=product, name=product.name, price=product.price, qty=2)

    order.recalc_totals()
    assert str(order.subtotal) == "400.00"
    assert str(order.discount_amount) == "50.00"
    assert str(order.total) == "350.00"
