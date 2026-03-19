"""Legal entity and address models."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel

from ..validators import validate_bik, validate_inn, validate_rs_with_bik

User = settings.AUTH_USER_MODEL


class LegalEntity(TimeStampedModel):
    name = models.CharField(max_length=255)
    inn = models.CharField(max_length=12, unique=True, validators=[validate_inn])
    bik = models.CharField(max_length=9, validators=[validate_bik])
    checking_account = models.CharField(max_length=20)
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    members = models.ManyToManyField(User, through="LegalEntityMembership", related_name="legal_entities")

    def clean(self) -> None:
        validate_rs_with_bik(self.checking_account, self.bik)

    def __str__(self) -> str:
        if self.inn:
            return f"{self.name} (ИНН {self.inn})"
        return self.name or f"Юрлицо #{self.pk}"


class MembershipRole(TimeStampedModel):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=64)

    def __str__(self) -> str:
        return self.name


class LegalEntityMembership(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.CASCADE)
    role = models.ForeignKey(MembershipRole, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        unique_together = (("user", "legal_entity"),)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.role_id is None:
            self.role, _ = MembershipRole.objects.get_or_create(code="manager", defaults={"name": "Менеджер"})
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        role = getattr(self.role, "name", "-")
        return f"{self.user} → {self.legal_entity} [{role}]"


class DeliveryAddress(TimeStampedModel):
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.CASCADE, related_name="delivery_addresses")
    label = models.CharField(max_length=255)
    country = models.CharField(max_length=128)
    city = models.CharField(max_length=128)
    street = models.CharField(max_length=255)
    postcode = models.CharField(max_length=32)
    details = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        unique_together = (("legal_entity", "label"),)

    def save(self, *args: Any, **kwargs: Any) -> None:
        super().save(*args, **kwargs)
        if self.is_default:
            DeliveryAddress.objects.filter(legal_entity=self.legal_entity, is_default=True).exclude(pk=self.pk).update(is_default=False)

    def __str__(self) -> str:
        return f"{self.label} — {self.city}, {self.street}"
