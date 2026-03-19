"""Seller split, seller order, and shipment models."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

from catalog.models import Product as CatalogProduct
from catalog.models import SellerOffer
from core.models import TimeStampedModel

from .base import Order, OrderItem

User = settings.AUTH_USER_MODEL


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
    canceled_qty = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"SellerOrderItem(seller_order={self.seller_order_id}, order_item={self.order_item_id})"

    @property
    def active_qty(self) -> int:
        return max(0, int(self.qty or 0) - int(self.canceled_qty or 0))


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
