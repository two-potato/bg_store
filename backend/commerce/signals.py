"""Commerce signals that enqueue downstream maintenance work."""

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
import logging

from .models import LegalEntityCreationRequest, SellerStore, LegalEntityMembership
from .tasks import (
    ensure_entity_and_membership_on_approval_task,
    reindex_products_on_seller_store_change_task,
    sync_company_workspace_on_membership_change_task,
)

log = logging.getLogger("commerce")


@receiver(post_save, sender=LegalEntityCreationRequest)
def ensure_entity_and_membership_on_approval(sender, instance: LegalEntityCreationRequest, created: bool, **kwargs):
    """Enqueue eventual-consistency repair when a creation request becomes approved."""
    status_code = getattr(getattr(instance, "status", None), "code", None)
    if status_code != "approved":
        return
    log.info("entity_creation_request_signal_approved", extra={"request_id": instance.id, "created_event": created, "applicant_id": instance.applicant_id, "inn": instance.inn})
    transaction.on_commit(lambda: ensure_entity_and_membership_on_approval_task.delay(request_id=instance.id))


@receiver([post_save, post_delete], sender=SellerStore)
def reindex_products_on_seller_store_change(sender, instance: SellerStore, **kwargs):
    """Enqueue seller product reindex after seller-store changes."""
    if not instance.owner_id:
        return
    transaction.on_commit(lambda: reindex_products_on_seller_store_change_task.delay(seller_id=instance.owner_id))


@receiver(post_save, sender=LegalEntityMembership)
def sync_company_workspace_on_membership_change(sender, instance: LegalEntityMembership, created: bool, **kwargs):
    """Enqueue company workspace synchronization after membership changes."""
    transaction.on_commit(lambda: sync_company_workspace_on_membership_change_task.delay(membership_id=instance.id))
