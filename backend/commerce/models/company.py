"""Company workspace and approval models."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel

from .legal import LegalEntity

User = settings.AUTH_USER_MODEL


class Company(TimeStampedModel):
    legal_entity = models.OneToOneField(LegalEntity, on_delete=models.CASCADE, related_name="company")
    display_name = models.CharField(max_length=255, blank=True, default="")
    procurement_email = models.EmailField(blank=True, default="")
    procurement_phone = models.CharField(max_length=32, blank=True, default="")
    invoice_email = models.EmailField(blank=True, default="")
    preferred_payment_method = models.CharField(max_length=32, blank=True, default="invoice")
    payment_comment = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Компания"
        verbose_name_plural = "Компании"

    def __str__(self) -> str:
        return self.display_name or self.legal_entity.name


class CompanyMembership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        BUYER = "buyer", "Buyer"
        APPROVER = "approver", "Approver"
        FINANCE = "finance", "Finance"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="company_memberships")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.BUYER)
    approval_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_default_approver = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "company"], name="unique_user_company_membership"),
        ]

    def __str__(self) -> str:
        return f"{self.user} -> {self.company} [{self.role}]"


class ApprovalPolicy(TimeStampedModel):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="approval_policy")
    is_enabled = models.BooleanField(default=False)
    auto_approve_below = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    require_approver_role = models.BooleanField(default=True)
    require_comment = models.BooleanField(default=False)
    required_approvals_count = models.PositiveIntegerField(default=1)
    max_pending_hours = models.PositiveIntegerField(default=24)

    class Meta:
        verbose_name = "Политика согласования"
        verbose_name_plural = "Политики согласования"

    def __str__(self) -> str:
        return f"ApprovalPolicy({self.company})"


class CompanyContact(TimeStampedModel):
    class Role(models.TextChoices):
        PROCUREMENT = "procurement", "Закупки"
        FINANCE = "finance", "Финансы"
        RECEIVING = "receiving", "Приёмка"
        OTHER = "other", "Прочее"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    role = models.CharField(max_length=24, choices=Role.choices, default=Role.PROCUREMENT)
    is_default = models.BooleanField(default=False)
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-is_default", "name", "id"]

    def save(self, *args: Any, **kwargs: Any) -> None:
        super().save(*args, **kwargs)
        if self.is_default:
            CompanyContact.objects.filter(company=self.company, is_default=True).exclude(pk=self.pk).update(is_default=False)

    def __str__(self) -> str:
        return f"{self.company} · {self.name}"
