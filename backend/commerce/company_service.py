from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .models import ApprovalPolicy, Company, CompanyMembership, LegalEntity, LegalEntityMembership


@dataclass
class ApprovalDecision:
    company: Company | None
    membership: CompanyMembership | None
    requires_approval: bool
    reason: str = ""


def ensure_company_workspace(legal_entity: LegalEntity) -> Company:
    company, _ = Company.objects.get_or_create(
        legal_entity=legal_entity,
        defaults={
            "display_name": legal_entity.name,
        },
    )
    return company


def sync_company_membership_from_legal_entity(membership: LegalEntityMembership) -> CompanyMembership:
    company = ensure_company_workspace(membership.legal_entity)
    role_map = {
        "owner": CompanyMembership.Role.OWNER,
        "admin": CompanyMembership.Role.ADMIN,
        "manager": CompanyMembership.Role.BUYER,
    }
    role_code = getattr(getattr(membership, "role", None), "code", "buyer")
    company_role = role_map.get(str(role_code), CompanyMembership.Role.BUYER)
    company_membership, _ = CompanyMembership.objects.update_or_create(
        user=membership.user,
        company=company,
        defaults={"role": company_role},
    )
    return company_membership


def resolve_order_approval_requirement(*, legal_entity: LegalEntity | None, user, order_total: Decimal) -> ApprovalDecision:
    if legal_entity is None or user is None or not getattr(user, "is_authenticated", False):
        return ApprovalDecision(company=None, membership=None, requires_approval=False)
    company = ensure_company_workspace(legal_entity)
    membership = CompanyMembership.objects.filter(company=company, user=user).first()
    if membership is None:
        base_membership = LegalEntityMembership.objects.select_related("role").filter(legal_entity=legal_entity, user=user).first()
        if base_membership:
            membership = sync_company_membership_from_legal_entity(base_membership)
    policy = getattr(company, "approval_policy", None)
    if policy is None or not policy.is_enabled:
        return ApprovalDecision(company=company, membership=membership, requires_approval=False)
    if membership and membership.role in {CompanyMembership.Role.OWNER, CompanyMembership.Role.ADMIN, CompanyMembership.Role.APPROVER}:
        return ApprovalDecision(company=company, membership=membership, requires_approval=False)
    if Decimal(str(order_total or 0)) < Decimal(str(policy.auto_approve_below or 0)):
        return ApprovalDecision(company=company, membership=membership, requires_approval=False)
    return ApprovalDecision(
        company=company,
        membership=membership,
        requires_approval=True,
        reason="Требуется согласование компании",
    )


def approver_memberships_for_company(company: Company):
    return CompanyMembership.objects.filter(
        company=company,
        role__in=[CompanyMembership.Role.OWNER, CompanyMembership.Role.ADMIN, CompanyMembership.Role.APPROVER],
    ).select_related("user")


def ensure_approval_policy(company: Company) -> ApprovalPolicy:
    policy, _ = ApprovalPolicy.objects.get_or_create(company=company)
    return policy
