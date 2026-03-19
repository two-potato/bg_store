from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from catalog.models import Brand, Category, Product
from core.models import TimeStampedModel


class PromotionRule(TimeStampedModel):
    class DiscountType(models.TextChoices):
        PERCENT = "percent", "Percent"
        FIXED = "fixed", "Fixed"

    class CustomerScope(models.TextChoices):
        ALL = "all", "All"
        AUTHENTICATED = "authenticated", "Authenticated only"
        GUEST = "guest", "Guest only"
        COMPANY = "company", "Company only"
        INDIVIDUAL = "individual", "Individual only"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    discount_type = models.CharField(max_length=16, choices=DiscountType.choices, default=DiscountType.PERCENT)
    discount_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    min_subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    customer_scope = models.CharField(max_length=24, choices=CustomerScope.choices, default=CustomerScope.ALL)
    stack_with_profile_discount = models.BooleanField(default=False)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="promotion_rules")
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name="promotion_rules")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="promotion_rules")
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promotion_rules",
    )

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name

    def is_live(self, now=None) -> bool:
        now = now or timezone.now()
        if not self.is_active:
            return False
        if self.starts_at and self.starts_at > now:
            return False
        if self.ends_at and self.ends_at < now:
            return False
        return True


class Coupon(TimeStampedModel):
    code = models.CharField(max_length=64, unique=True, db_index=True)
    rule = models.ForeignKey(PromotionRule, on_delete=models.PROTECT, related_name="coupons")
    is_active = models.BooleanField(default=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    per_user_limit = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class PromotionRedemption(TimeStampedModel):
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="redemptions")
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="promotion_redemptions")
    redeemed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promotion_redemptions",
    )
    guest_email = models.EmailField(blank=True, default="")
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["coupon", "order"], name="unique_coupon_redemption_per_order"),
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.coupon.code} -> order {self.order_id}"
