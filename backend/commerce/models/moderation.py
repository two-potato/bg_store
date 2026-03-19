"""Moderation request models."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel

from ..validators import validate_bik, validate_inn
from .legal import LegalEntity

User = settings.AUTH_USER_MODEL


class RequestStatus(TimeStampedModel):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=64)

    def __str__(self) -> str:
        return self.name


class MembershipRequest(TimeStampedModel):
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="membership_requests")
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.CASCADE, related_name="membership_requests")
    comment = models.TextField(blank=True, null=True)
    status = models.ForeignKey(RequestStatus, on_delete=models.PROTECT, null=True, blank=True)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.status_id is None:
            self.status, _ = RequestStatus.objects.get_or_create(code="pending", defaults={"name": "На рассмотрении"})
        super().save(*args, **kwargs)


class LegalEntityCreationRequest(TimeStampedModel):
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="entity_creation_requests")
    name = models.CharField(max_length=255)
    inn = models.CharField(max_length=12, validators=[validate_inn])
    bik = models.CharField(max_length=9, validators=[validate_bik])
    checking_account = models.CharField(max_length=20)
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    status = models.ForeignKey(RequestStatus, on_delete=models.PROTECT, null=True, blank=True)

    def clean(self) -> None:
        pass

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.status_id is None:
            self.status, _ = RequestStatus.objects.get_or_create(code="pending", defaults={"name": "На рассмотрении"})
        super().save(*args, **kwargs)
