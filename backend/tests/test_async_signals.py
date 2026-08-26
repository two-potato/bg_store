import pytest

from catalog.models import Brand, Category, Product
from commerce.models import (
    LegalEntity,
    LegalEntityCreationRequest,
    LegalEntityMembership,
    MembershipRole,
    RequestStatus,
    SellerStore,
)


pytestmark = pytest.mark.django_db


def test_product_save_schedules_async_search_upsert(monkeypatch):
    calls: list[int] = []

    def fake_delay(*, product_id: int):
        calls.append(product_id)

    monkeypatch.setattr("catalog.signals.upsert_product_in_search.delay", fake_delay)
    monkeypatch.setattr("catalog.signals.transaction.on_commit", lambda callback: callback())

    brand = Brand.objects.create(name="Signal Brand")
    category = Category.objects.create(name="Signal Category")
    product = Product.objects.create(
        sku="10000001",
        name="Signal Product",
        brand=brand,
        category=category,
        price=100,
        stock_qty=5,
    )

    assert calls == [product.id]


def test_product_delete_schedules_async_search_delete(monkeypatch):
    calls: list[int] = []

    def fake_delay(*, product_id: int):
        calls.append(product_id)

    monkeypatch.setattr("catalog.signals.delete_product_from_search.delay", fake_delay)
    monkeypatch.setattr("catalog.signals.transaction.on_commit", lambda callback: callback())

    brand = Brand.objects.create(name="Delete Brand")
    category = Category.objects.create(name="Delete Category")
    product = Product.objects.create(
        sku="10000002",
        name="Delete Product",
        brand=brand,
        category=category,
        price=100,
        stock_qty=5,
    )
    product_id = product.id
    calls.clear()

    product.delete()

    assert calls == [product_id]


def test_membership_change_schedules_workspace_sync(monkeypatch, user):
    calls: list[int] = []

    def fake_delay(*, membership_id: int):
        calls.append(membership_id)

    monkeypatch.setattr("commerce.signals.sync_company_workspace_on_membership_change_task.delay", fake_delay)
    monkeypatch.setattr("commerce.signals.transaction.on_commit", lambda callback: callback())

    role = MembershipRole.objects.get_or_create(code="manager", defaults={"name": "Менеджер"})[0]
    legal_entity = LegalEntity.objects.create(
        name="Signal LE",
        inn="7707083893",
        bik="044525225",
        checking_account="40702810900000000001",
    )
    membership = LegalEntityMembership.objects.create(user=user, legal_entity=legal_entity, role=role)

    assert calls == [membership.id]


def test_approved_creation_request_schedules_repair_task(monkeypatch, user):
    calls: list[int] = []

    def fake_delay(*, request_id: int):
        calls.append(request_id)

    monkeypatch.setattr("commerce.signals.ensure_entity_and_membership_on_approval_task.delay", fake_delay)
    monkeypatch.setattr("commerce.signals.transaction.on_commit", lambda callback: callback())

    approved = RequestStatus.objects.get_or_create(code="approved", defaults={"name": "Одобрено"})[0]
    request = LegalEntityCreationRequest.objects.create(
        applicant=user,
        name="Approved LLC",
        inn="7707083894",
        bik="044525225",
        checking_account="40702810900000000004",
        status=approved,
    )

    assert calls == [request.id]


def test_seller_store_change_schedules_reindex(monkeypatch, user):
    calls: list[int] = []

    def fake_delay(*, seller_id: int):
        calls.append(seller_id)

    monkeypatch.setattr("commerce.signals.reindex_products_on_seller_store_change_task.delay", fake_delay)
    monkeypatch.setattr("commerce.signals.transaction.on_commit", lambda callback: callback())

    legal_entity = LegalEntity.objects.create(
        name="Store LE",
        inn="7707083895",
        bik="044525225",
        checking_account="40702810900000000005",
    )
    store = SellerStore.objects.create(owner=user, legal_entity=legal_entity, name="Signal Store")

    assert calls == [user.id]

    calls.clear()
    store.description = "Updated"
    store.save(update_fields=["description"])

    assert calls == [user.id]
