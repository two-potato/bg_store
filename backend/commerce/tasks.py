"""Asynchronous commerce maintenance tasks."""

from __future__ import annotations

import logging

from celery import shared_task

from catalog.tasks import reindex_products_for_seller
from commerce.company_service import ensure_company_workspace, sync_company_membership_from_legal_entity
from commerce.models import ApprovalPolicy, LegalEntity, LegalEntityCreationRequest, LegalEntityMembership, MembershipRole

log = logging.getLogger("commerce")


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def ensure_entity_and_membership_on_approval_task(self, request_id: int) -> None:
    """Ensure the entity and owner membership exist for an approved creation request."""
    instance = (
        LegalEntityCreationRequest.objects.select_related("status", "applicant")
        .filter(pk=request_id)
        .first()
    )
    if instance is None:
        log.info("entity_creation_request_signal_skip_missing", extra={"request_id": request_id})
        return
    status_code = getattr(getattr(instance, "status", None), "code", None)
    if status_code != "approved":
        log.info("entity_creation_request_signal_skip_not_approved", extra={"request_id": request_id, "status": status_code})
        return

    le = LegalEntity.objects.filter(inn=instance.inn).first()
    if not le:
        le = LegalEntity.objects.create(
            name=instance.name,
            inn=instance.inn,
            bik=instance.bik,
            checking_account=instance.checking_account,
            bank_name=instance.bank_name,
        )
        log.info("entity_created_from_signal", extra={"request_id": instance.id, "legal_entity_id": le.id, "inn": instance.inn})

    owner_role, _ = MembershipRole.objects.get_or_create(code="owner", defaults={"name": "Владелец"})
    membership, created_membership = LegalEntityMembership.objects.get_or_create(
        user=instance.applicant,
        legal_entity=le,
        defaults={"role": owner_role},
    )
    log.info(
        "entity_membership_ensured_from_signal",
        extra={
            "request_id": instance.id,
            "membership_id": membership.id,
            "membership_created": created_membership,
            "applicant_id": instance.applicant_id,
            "legal_entity_id": le.id,
        },
    )


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def sync_company_workspace_on_membership_change_task(self, membership_id: int) -> None:
    """Ensure company workspace artifacts exist for a legal-entity membership."""
    membership = LegalEntityMembership.objects.select_related("legal_entity", "role", "user").filter(pk=membership_id).first()
    if membership is None:
        log.info("membership_workspace_sync_skip_missing", extra={"membership_id": membership_id})
        return
    company = ensure_company_workspace(membership.legal_entity)
    sync_company_membership_from_legal_entity(membership)
    ApprovalPolicy.objects.get_or_create(company=company)
    log.info("membership_workspace_synced", extra={"membership_id": membership_id, "company_id": company.id})


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def reindex_products_on_seller_store_change_task(self, seller_id: int) -> None:
    """Schedule reindex of all seller products after seller-store changes."""
    reindex_products_for_seller.delay(seller_id=seller_id)


# Transitional registration: commerce is installed and autodiscovered by Celery,
# so importing the legacy module keeps existing task names alive while their
# implementation is moved out of the former storefront package.
from shopfront import tasks as _legacy_shopfront_tasks  # noqa: E402,F401
