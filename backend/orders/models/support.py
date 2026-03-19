"""Approval, claim, and support-ticket order models."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel

from .base import Order

User = settings.AUTH_USER_MODEL


class OrderApprovalLog(TimeStampedModel):
    class Decision(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="approval_logs")
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="order_approval_logs")
    decision = models.CharField(max_length=16, choices=Decision.choices)
    comment = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"OrderApprovalLog(order={self.order_id}, actor={self.actor_id}, decision={self.decision})"


class OrderClaim(TimeStampedModel):
    class ClaimType(models.TextChoices):
        RETURN = "return", "Возврат"
        DAMAGE = "damage", "Повреждение"
        SHORTAGE = "shortage", "Недовложение"
        DELIVERY = "delivery", "Проблема доставки"
        OTHER = "other", "Другое"

    class Status(models.TextChoices):
        OPEN = "open", "Открыто"
        IN_REVIEW = "in_review", "На рассмотрении"
        RESOLVED = "resolved", "Решено"
        REJECTED = "rejected", "Отклонено"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="claims")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="order_claims")
    claim_type = models.CharField(max_length=24, choices=ClaimType.choices, default=ClaimType.OTHER)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.OPEN)
    message = models.TextField()
    seller_response = models.TextField(blank=True, default="")
    resolution_comment = models.TextField(blank=True, default="")
    responded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="responded_order_claims")

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="orderclaim_status_created_idx"),
        ]

    def __str__(self):
        return f"OrderClaim(order={self.order_id}, created_by={self.created_by_id}, status={self.status})"


class OrderSupportTicket(TimeStampedModel):
    class Topic(models.TextChoices):
        SUPPORT = "support", "Поддержка"
        PAYMENT = "payment", "Платёж"
        DELIVERY = "delivery", "Доставка"
        DOCUMENTS = "documents", "Документы"

    class Status(models.TextChoices):
        OPEN = "open", "Открыт"
        IN_PROGRESS = "in_progress", "В работе"
        RESOLVED = "resolved", "Решён"
        CLOSED = "closed", "Закрыт"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="support_tickets")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="order_support_tickets")
    topic = models.CharField(max_length=24, choices=Topic.choices, default=Topic.SUPPORT)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.OPEN)
    subject = models.CharField(max_length=255)
    message = models.TextField()
    resolution_comment = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="ordersupport_status_idx"),
        ]

    def __str__(self):
        return f"OrderSupportTicket(order={self.order_id}, created_by={self.created_by_id}, status={self.status})"
