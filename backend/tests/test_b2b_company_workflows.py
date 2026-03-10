import pytest
from django.contrib.auth import get_user_model

from commerce.company_service import ensure_company_workspace, ensure_approval_policy, resolve_order_approval_requirement
from commerce.models import CompanyMembership, LegalEntity, LegalEntityMembership, MembershipRole
from orders.models import Order


pytestmark = pytest.mark.django_db


def test_company_workspace_syncs_from_legal_entity_membership():
    User = get_user_model()
    user = User.objects.create_user(username="company_buyer", password="pass")
    role = MembershipRole.objects.get_or_create(code="manager", defaults={"name": "Менеджер"})[0]
    legal_entity = LegalEntity.objects.create(name="B2B LE", inn="500100012101", bik="044525225", checking_account="40702810900000002101")

    LegalEntityMembership.objects.create(user=user, legal_entity=legal_entity, role=role)

    company = ensure_company_workspace(legal_entity)
    membership = CompanyMembership.objects.get(company=company, user=user)

    assert company.legal_entity == legal_entity
    assert membership.role == CompanyMembership.Role.BUYER


def test_approval_policy_requires_approver_above_threshold():
    User = get_user_model()
    buyer = User.objects.create_user(username="approval_buyer", password="pass")
    approver = User.objects.create_user(username="approval_admin", password="pass")
    legal_entity = LegalEntity.objects.create(name="Approval LE", inn="500100012102", bik="044525225", checking_account="40702810900000002102")
    company = ensure_company_workspace(legal_entity)
    policy = ensure_approval_policy(company)
    policy.is_enabled = True
    policy.auto_approve_below = 1000
    policy.save(update_fields=["is_enabled", "auto_approve_below"])
    CompanyMembership.objects.create(user=buyer, company=company, role=CompanyMembership.Role.BUYER)
    CompanyMembership.objects.create(user=approver, company=company, role=CompanyMembership.Role.APPROVER)

    decision = resolve_order_approval_requirement(legal_entity=legal_entity, user=buyer, order_total=1500)
    approver_decision = resolve_order_approval_requirement(legal_entity=legal_entity, user=approver, order_total=1500)

    assert decision.requires_approval is True
    assert approver_decision.requires_approval is False


def test_account_approver_can_approve_company_order(client, db):
    User = get_user_model()
    approver = User.objects.create_user(username="approver_user", password="pass")
    buyer = User.objects.create_user(username="buyer_user", password="pass")
    legal_entity = LegalEntity.objects.create(name="Account Approval LE", inn="500100012103", bik="044525225", checking_account="40702810900000002103")
    company = ensure_company_workspace(legal_entity)
    admin_role = MembershipRole.objects.get_or_create(code="admin", defaults={"name": "Админ"})[0]
    manager_role = MembershipRole.objects.get_or_create(code="manager", defaults={"name": "Менеджер"})[0]
    LegalEntityMembership.objects.create(user=approver, legal_entity=legal_entity, role=admin_role)
    LegalEntityMembership.objects.create(user=buyer, legal_entity=legal_entity, role=manager_role)
    CompanyMembership.objects.update_or_create(
        user=approver,
        company=company,
        defaults={"role": CompanyMembership.Role.APPROVER},
    )
    CompanyMembership.objects.update_or_create(
        user=buyer,
        company=company,
        defaults={"role": CompanyMembership.Role.BUYER},
    )
    order = Order.objects.create(
        legal_entity=legal_entity,
        placed_by=buyer,
        requested_by=buyer,
        customer_type=Order.CustomerType.COMPANY,
        approval_status=Order.ApprovalStatus.PENDING,
        total=1200,
    )

    assert client.login(username="approver_user", password="pass")
    detail = client.get(f"/account/orders/{order.id}/")
    assert detail.status_code == 200
    response = client.post(f"/account/orders/{order.id}/approval/", {"action": "approve", "comment": "ok"})

    assert response.status_code == 302
    order.refresh_from_db()
    assert order.approval_status == Order.ApprovalStatus.APPROVED
    assert order.approved_by == approver
