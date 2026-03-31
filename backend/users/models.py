from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from core.models import TimeStampedModel

class User(AbstractUser):
    email = models.EmailField(blank=True, null=True)

class Friendship(TimeStampedModel):
    """Tracks friendship requests/acceptances between users."""
    from_user = models.ForeignKey('User', related_name='friendships_initiated', on_delete=models.CASCADE)
    to_user = models.ForeignKey('User', related_name='friendships_received', on_delete=models.CASCADE)
    accepted = models.BooleanField(default=False)

    class Meta:
        unique_together = (('from_user', 'to_user'),)

    def __str__(self):
        return f"{self.from_user} -> {self.to_user} ({'accepted' if self.accepted else 'pending'})"

    def clean(self):
        super().clean()
        if self.from_user_id and self.to_user_id and self.from_user_id == self.to_user_id:
            raise ValidationError({"to_user": "Cannot create friendship with yourself."})

    def save(self, *args, **kwargs):
        if (
            self.from_user_id
            and self.to_user_id
            and self.from_user_id == self.to_user_id
        ):
            raise ValidationError({"to_user": "Cannot create friendship with yourself."})
        if self.pk is None and self.from_user_id and self.to_user_id:
            existing = Friendship.objects.filter(
                from_user_id=self.from_user_id,
                to_user_id=self.to_user_id,
            ).first()
            if existing is not None:
                self.pk = existing.pk
                self.created_at = existing.created_at
                self.updated_at = existing.updated_at
                if self.accepted and not existing.accepted:
                    Friendship.objects.filter(pk=existing.pk).update(accepted=True)
                    existing.refresh_from_db(fields=["updated_at", "accepted"])
                    self.accepted = existing.accepted
                    self.updated_at = existing.updated_at
                else:
                    self.accepted = existing.accepted
                return
        self.full_clean()
        super().save(*args, **kwargs)

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=255, blank=True, default="")
    contact_email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, null=True)
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    telegram_username = models.CharField(max_length=255, blank=True, null=True)
    notify_email_orders = models.BooleanField(default=True)
    notify_email_marketing = models.BooleanField(default=False)
    notify_telegram_orders = models.BooleanField(default=True)
    notify_telegram_marketing = models.BooleanField(default=False)
    discount = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    photo = models.ImageField(upload_to='user_photos/', null=True, blank=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=False)
    friends = models.ManyToManyField('self', through=Friendship, symmetrical=False, blank=True, related_name='friend_of')
    class Role(models.TextChoices):
        ADMIN = "admin", "Админ"
        MANAGER = "manager", "Менеджер"
        CLIENT = "client", "Клиент"
        SELLER = "seller", "Продавец"
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.CLIENT)

    def __str__(self):
        return f"{self.user.username} profile"

    def save(self, *args, **kwargs):
        if not self.slug:
            source = self.full_name or self.user.username or f"user-{self.user_id}"
            base = slugify(source) or f"user-{self.user_id or 'x'}"
            candidate = base
            suffix = 2
            while UserProfile.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{suffix}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)
