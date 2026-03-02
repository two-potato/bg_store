from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User, UserProfile


@receiver(post_save, sender=User)
def ensure_profile_for_user(sender, instance: User, created: bool, **kwargs):
    if created:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={
                "full_name": (instance.get_full_name() or instance.username or "").strip(),
                "contact_email": (instance.email or "").strip(),
            },
        )
