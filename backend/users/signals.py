from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

from .models import User, UserProfile

log = logging.getLogger("users")


@receiver(post_save, sender=User)
def ensure_profile_for_user(sender, instance: User, created: bool, **kwargs):
    if created:
        profile, profile_created = UserProfile.objects.get_or_create(
            user=instance,
            defaults={
                "full_name": (instance.get_full_name() or instance.username or "").strip(),
                "contact_email": (instance.email or "").strip(),
            },
        )
        log.info(
            "user_profile_ensured_on_user_create",
            extra={
                "user_id": instance.id,
                "profile_id": profile.id,
                "profile_created": profile_created,
            },
        )


@receiver(post_save, sender=User)
def sync_profile_email_from_user(sender, instance: User, created: bool, **kwargs):
    email = (instance.email or "").strip()
    profile, _ = UserProfile.objects.get_or_create(
        user=instance,
        defaults={
            "full_name": (instance.get_full_name() or instance.username or "").strip(),
            "contact_email": email,
        },
    )
    if (profile.contact_email or "").strip() != email:
        UserProfile.objects.filter(pk=profile.pk).update(contact_email=email)
        log.info(
            "user_email_synced_to_profile",
            extra={"user_id": instance.id, "profile_id": profile.id},
        )


@receiver(post_save, sender=UserProfile)
def sync_user_email_from_profile(sender, instance: UserProfile, created: bool, **kwargs):
    email = (instance.contact_email or "").strip()
    user = instance.user
    if (user.email or "").strip() != email:
        User.objects.filter(pk=user.pk).update(email=email)
        log.info(
            "profile_email_synced_to_user",
            extra={"user_id": user.id, "profile_id": instance.id},
        )
