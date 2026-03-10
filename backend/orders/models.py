from django.db import models
from django.conf import settings
from decimal import Decimal
from uuid import uuid4
from django_fsm import FSMField, transition
from core.models import TimeStampedModel
from commerce.models import LegalEntity, DeliveryAddress
from catalog.models import Product as CatalogProduct
from catalog.models import SellerOffer

User = settings.AUTH_USER_MODEL

class Order(TimeStampedModel):
    class SourceChannel(models.TextChoices):
        WEB = "web", "Web"
        TWA = "twa", "Telegram Web App"
        API = "api", "API"

    class SplitStatus(models.TextChoices):
        SINGLE = "single", "Single seller"
        PLANNED = "planned", "Split planned"
        READY = "ready", "Split ready"
        SPLIT = "split", "Split executed"
    class ApprovalStatus(models.TextChoices):
        NOT_REQUIRED = "not_required", "Approval not required"
        PENDING = "pending", "Pending approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

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
    placed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="placed_orders", null=True, blank=True)
    delivery_address = models.ForeignKey(DeliveryAddress, on_delete=models.PROTECT, related_name="orders", null=True, blank=True)
    # For individual checkout
    customer_name = models.CharField(max_length=255, blank=True, null=True)
    customer_email = models.EmailField(blank=True, null=True)
    customer_phone = models.CharField(max_length=64, blank=True, null=True)
    address_text = models.CharField(max_length=512, blank=True, null=True)
    guest_access_token = models.CharField(max_length=40, blank=True, default="", db_index=True)
    customer_comment = models.TextField(blank=True, default="")
    coupon_code = models.CharField(max_length=64, blank=True, default="")
    source_channel = models.CharField(max_length=16, choices=SourceChannel.choices, default=SourceChannel.WEB)
    split_status = models.CharField(max_length=16, choices=SplitStatus.choices, default=SplitStatus.SINGLE)
    approval_status = models.CharField(max_length=16, choices=ApprovalStatus.choices, default=ApprovalStatus.NOT_REQUIRED)
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="requested_orders", null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="approved_orders", null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    def profile_discount_percent(self) -> Decimal:
        if not self.placed_by_id:
            return Decimal("0.00")
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

    def recalc_totals(self, explicit_discount_amount: Decimal | None = None):
        items = list(self.items.all())
        self.subtotal = sum((i.price * i.qty for i in items), start=Decimal("0.00")).quantize(Decimal("0.01"))
        if explicit_discount_amount is None:
            discount_pct = self.profile_discount_percent()
            self.discount_amount = (self.subtotal * discount_pct / Decimal("100.00")).quantize(Decimal("0.01"))
        else:
            self.discount_amount = min(
                self.subtotal,
                Decimal(str(explicit_discount_amount)).quantize(Decimal("0.01")),
            )
        self.total = (self.subtotal - self.discount_amount).quantize(Decimal("0.01"))

    @property
    def is_guest(self) -> bool:
        return not bool(self.placed_by_id)

    def buyer_display(self) -> str:
        if self.placed_by_id:
            return str(self.placed_by)
        if self.customer_name:
            return self.customer_name
        if self.customer_email:
            return self.customer_email
        if self.customer_phone:
            return self.customer_phone
        return f"Guest #{self.id or 'new'}"

    @property
    def requires_approval(self) -> bool:
        return self.approval_status == self.ApprovalStatus.PENDING

    def ensure_guest_access_token(self) -> str:
        if self.guest_access_token:
            return self.guest_access_token
        self.guest_access_token = uuid4().hex
        return self.guest_access_token

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
    seller_offer = models.ForeignKey(SellerOffer, on_delete=models.PROTECT, null=True, blank=True, related_name="order_items")
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    qty = models.PositiveIntegerField(default=1)

    @property
    def seller_user(self):
        if self.seller_offer_id:
            return self.seller_offer.seller
        return getattr(self.product, "seller", None)


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


class OrderSellerSplit(TimeStampedModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        READY = "ready", "Ready"
        SENT = "sent", "Sent"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="seller_splits")
    seller = models.ForeignKey(User, on_delete=models.PROTECT, related_name="order_seller_splits")
    seller_store_name = models.CharField(max_length=255, blank=True, default="")
    items_count = models.PositiveIntegerField(default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "seller"], name="unique_seller_split_per_order"),
        ]
        indexes = [
            models.Index(fields=["seller", "-created_at"], name="order_split_seller_created_idx"),
        ]

    def __str__(self):
        return f"OrderSellerSplit(order={self.order_id}, seller={self.seller_id}, status={self.status})"


class SellerOrder(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "new", "New"
        ACCEPTED = "accepted", "Accepted"
        PICKING = "picking", "Picking"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELED = "canceled", "Canceled"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="seller_orders")
    seller = models.ForeignKey(User, on_delete=models.PROTECT, related_name="seller_orders")
    seller_store_name = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW)
    customer_comment = models.TextField(blank=True, default="")
    internal_comment = models.TextField(blank=True, default="")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    accepted_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "seller"], name="unique_seller_order_per_order"),
        ]
        indexes = [
            models.Index(fields=["seller", "status", "-created_at"], name="sellerorder_status_idx"),
        ]

    def __str__(self):
        return f"SellerOrder(order={self.order_id}, seller={self.seller_id}, status={self.status})"


class SellerOrderItem(TimeStampedModel):
    seller_order = models.ForeignKey(SellerOrder, on_delete=models.CASCADE, related_name="items")
    order_item = models.OneToOneField(OrderItem, on_delete=models.CASCADE, related_name="seller_order_item")
    product = models.ForeignKey(CatalogProduct, on_delete=models.PROTECT)
    seller_offer = models.ForeignKey(SellerOffer, on_delete=models.PROTECT, null=True, blank=True, related_name="seller_order_items")
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    qty = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"SellerOrderItem(seller_order={self.seller_order_id}, order_item={self.order_item_id})"


class Shipment(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"
        IN_TRANSIT = "in_transit", "In transit"
        DELIVERED = "delivered", "Delivered"
        ISSUE = "issue", "Issue"

    seller_order = models.ForeignKey(SellerOrder, on_delete=models.CASCADE, related_name="shipments")
    tracking_number = models.CharField(max_length=120, blank=True, default="")
    delivery_method = models.CharField(max_length=120, blank=True, default="")
    warehouse_name = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    packed_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="shipment_status_created_idx"),
        ]

    def __str__(self):
        return f"Shipment(seller_order={self.seller_order_id}, tracking={self.tracking_number})"


class ShipmentItem(TimeStampedModel):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="items")
    seller_order_item = models.ForeignKey(SellerOrderItem, on_delete=models.CASCADE, related_name="shipment_items")
    qty = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["shipment", "seller_order_item"], name="unique_shipment_seller_order_item"),
        ]

    def __str__(self):
        return f"ShipmentItem(shipment={self.shipment_id}, seller_order_item={self.seller_order_item_id})"


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
