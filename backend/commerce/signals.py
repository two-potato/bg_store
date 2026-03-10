from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
import logging

from catalog.es_index import upsert_product
from catalog.models import Product

from .models import (
    ApprovalPolicy,
    LegalEntityCreationRequest,
    LegalEntity,
    LegalEntityMembership,
    MembershipRole,
    SellerStore,
)
from .company_service import ensure_company_workspace, sync_company_membership_from_legal_entity

log = logging.getLogger("commerce")


@receiver(post_save, sender=LegalEntityCreationRequest)
def ensure_entity_and_membership_on_approval(sender, instance: LegalEntityCreationRequest, created: bool, **kwargs):
    """When a creation request becomes approved, ensure user gets membership and entity exists.

    This makes the system eventual-consistent even if approval happened outside
    of the usual API/admin flows.
    """
    # Proceed only when request is approved (status is FK with code field)
    status_code = getattr(getattr(instance, "status", None), "code", None)
    if status_code != "approved":
        return
    log.info("entity_creation_request_signal_approved", extra={"request_id": instance.id, "created_event": created, "applicant_id": instance.applicant_id, "inn": instance.inn})

    # Try to find or create LegalEntity by INN
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
    # Ensure membership for applicant
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


@receiver([post_save, post_delete], sender=SellerStore)
def reindex_products_on_seller_store_change(sender, instance: SellerStore, **kwargs):
    products = Product.objects.select_related("brand", "category", "country_of_origin", "seller", "seller__seller_store").filter(
        seller=instance.owner
    )
    for product in products.iterator(chunk_size=200):
        upsert_product(product)


@receiver(post_save, sender=LegalEntityMembership)
def sync_company_workspace_on_membership_change(sender, instance: LegalEntityMembership, created: bool, **kwargs):
    company = ensure_company_workspace(instance.legal_entity)
    sync_company_membership_from_legal_entity(instance)
    ApprovalPolicy.objects.get_or_create(company=company)
