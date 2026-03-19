"""Marketplace seller-store models."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from core.models import TimeStampedModel

from .legal import LegalEntity

User = settings.AUTH_USER_MODEL


class SellerStore(TimeStampedModel):
    class ModerationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        SUSPENDED = "suspended", "Suspended"

    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name="seller_store")
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.PROTECT, related_name="seller_stores")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=False)
    description = models.TextField(blank=True, default="")
    photo = models.ImageField(upload_to="seller_store_photos/", null=True, blank=True)
    moderation_status = models.CharField(max_length=16, choices=ModerationStatus.choices, default=ModerationStatus.PENDING)
    moderation_note = models.CharField(max_length=255, blank=True, default="")
    sla_target_hours = models.PositiveIntegerField(default=24)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_featured = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Магазин продавца"
        verbose_name_plural = "Магазины продавцов"

    def __str__(self) -> str:
        return f"{self.name} — {self.owner}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            base = slugify(self.name) or f"store-{self.owner_id or 'x'}"
            candidate = base
            suffix = 2
            while SellerStore.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{suffix}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)


class StoreReview(TimeStampedModel):
    store = models.ForeignKey(SellerStore, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="store_reviews")
    rating = models.PositiveSmallIntegerField()
    text = models.TextField(blank=True, default="")
    is_verified_buyer = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["store", "user"], name="unique_store_review_per_user"),
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"StoreReview(store={self.store_id}, user={self.user_id}, rating={self.rating})"
