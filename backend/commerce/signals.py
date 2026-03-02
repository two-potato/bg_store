from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import LegalEntityCreationRequest, LegalEntity, LegalEntityMembership, MembershipRole


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
    # Ensure membership for applicant
    owner_role, _ = MembershipRole.objects.get_or_create(code="owner", defaults={"name": "Владелец"})
    LegalEntityMembership.objects.get_or_create(
        user=instance.applicant,
        legal_entity=le,
        defaults={"role": owner_role},
    )
