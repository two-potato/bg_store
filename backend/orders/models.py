from django.db import models
from django.conf import settings
from decimal import Decimal
from django_fsm import FSMField, transition
from core.models import TimeStampedModel
from commerce.models import LegalEntity, DeliveryAddress
from catalog.models import Product as CatalogProduct

User = settings.AUTH_USER_MODEL

class Order(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "new", "Новый"
        CONFIRMED = "confirmed", "Подтвержден"
        PAID = "paid", "Оплачен"
        DELIVERING = "delivering", "В работе"
        DELIVERED = "delivered", "Выполнен"
        CANCELED = "canceled", "Отменен"
        CHANGED = "changed", "Изменен"
    class CustomerType(models.TextChoices):
        INDIVIDUAL = "individual", "Физ. лицо"
        COMPANY = "company", "Юр. лицо"
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Наличные"
        INVOICE = "invoice", "По счёту"
        MIR_CARD = "mir_card", "Карта МИР"

    status = FSMField(default=Status.NEW, choices=Status.choices, protected=False)
    customer_type = models.CharField(max_length=16, choices=CustomerType.choices, default=CustomerType.COMPANY)
    payment_method = models.CharField(max_length=16, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.PROTECT, related_name="orders", null=True, blank=True)
    placed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="placed_orders")
    delivery_address = models.ForeignKey(DeliveryAddress, on_delete=models.PROTECT, related_name="orders", null=True, blank=True)
    # For individual checkout
    customer_name = models.CharField(max_length=255, blank=True, null=True)
    customer_phone = models.CharField(max_length=64, blank=True, null=True)
    address_text = models.CharField(max_length=512, blank=True, null=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    def profile_discount_percent(self) -> Decimal:
        profile = getattr(self.placed_by, "profile", None)
        raw = getattr(profile, "discount", Decimal("0.00")) if profile else Decimal("0.00")
        try:
            pct = Decimal(str(raw))
        except Exception:
            pct = Decimal("0.00")
        if pct < 0:
            return Decimal("0.00")
        if pct > 100:
            return Decimal("100.00")
        return pct

    def recalc_totals(self):
        items = list(self.items.all())
        self.subtotal = sum((i.price * i.qty for i in items), start=Decimal("0.00")).quantize(Decimal("0.01"))
        discount_pct = self.profile_discount_percent()
        self.discount_amount = (self.subtotal * discount_pct / Decimal("100.00")).quantize(Decimal("0.01"))
        self.total = (self.subtotal - self.discount_amount).quantize(Decimal("0.01"))

    @transition(field=status, source=[Status.NEW, Status.CHANGED], target=Status.CONFIRMED)
    def approve(self):
        ...

    @transition(field=status, source=Status.CONFIRMED, target=Status.PAID)
    def pay(self):
        ...

    @transition(field=status, source=Status.PAID, target=Status.DELIVERING)
    def ship(self):
        ...

    @transition(field=status, source=Status.DELIVERING, target=Status.DELIVERED)
    def complete(self):
        ...

    @transition(field=status, source="*", target=Status.CANCELED)
    def cancel(self):
        ...

    @transition(field=status, source="*", target=Status.CHANGED)
    def mark_changed(self):
        ...

class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(CatalogProduct, on_delete=models.PROTECT)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    qty = models.PositiveIntegerField(default=1)


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
