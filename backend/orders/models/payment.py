"""Payment-related order models."""

from __future__ import annotations

from decimal import Decimal

from django.db import models

from core.models import TimeStampedModel

from .base import Order


class FakeAcquiringPayment(TimeStampedModel):
    class Status(models.TextChoices):
        CREATED = "created", "Создан"
        PROCESSING = "processing", "В обработке"
        REQUIRES_3DS = "requires_3ds", "Требуется 3DS"
        PAID = "paid", "Оплачен"
        FAILED = "failed", "Ошибка"
        CANCELED = "canceled", "Отменен"
        REFUNDED = "refunded", "Возврат"

    class Event(models.TextChoices):
        START = "start", "Инициация"
        SUCCESS = "success", "Успешная оплата"
        FAIL = "fail", "Ошибка оплаты"
        CANCEL = "cancel", "Отмена пользователем"
        REQUIRE_3DS = "require_3ds", "Запрос 3DS"
        PASS_3DS = "pass_3ds", "3DS успешно"
        REFUND = "refund", "Возврат"

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="fake_payment")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    provider_payment_id = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.CREATED)
    last_event = models.CharField(max_length=24, choices=Event.choices, default=Event.START)
    history = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"fake-pay:{self.provider_payment_id} order={self.order_id} status={self.status}"
