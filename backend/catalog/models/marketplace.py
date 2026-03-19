from django.conf import settings
from django.db import models

from core.models import TimeStampedModel

from .product import Product


class SellerOffer(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        OUT_OF_STOCK = "out_of_stock", "Out of stock"
        ARCHIVED = "archived", "Archived"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="seller_offers")
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="seller_offers")
    seller_store = models.ForeignKey("commerce.SellerStore", on_delete=models.SET_NULL, null=True, blank=True, related_name="offers")
    offer_title = models.CharField(max_length=255, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    min_order_qty = models.PositiveIntegerField(default=1)
    lead_time_days = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    is_featured = models.BooleanField(default=False)
    warehouse_source = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-is_featured", "price", "id"]
        constraints = [
            models.UniqueConstraint(fields=["product", "seller"], name="unique_product_seller_offer"),
        ]
        indexes = [
            models.Index(fields=["product", "status", "price"], name="selleroffer_prod_price_idx"),
            models.Index(fields=["seller", "status", "price"], name="selleroffer_seller_price_idx"),
        ]

    def __str__(self):
        return f"Offer(product={self.product_id}, seller={self.seller_id}, price={self.price})"

    @property
    def available_stock_qty(self) -> int:
        inventories = list(getattr(self, "_prefetched_objects_cache", {}).get("inventories", []) or [])
        if inventories:
            return sum(max(0, inv.available_qty) for inv in inventories)
        return max(0, int(getattr(self, "stock_qty_fallback", 0) or 0))


class SellerInventory(TimeStampedModel):
    offer = models.ForeignKey(SellerOffer, on_delete=models.CASCADE, related_name="inventories")
    warehouse_name = models.CharField(max_length=120)
    warehouse_code = models.CharField(max_length=64, blank=True)
    stock_qty = models.IntegerField(default=0)
    reserved_qty = models.IntegerField(default=0)
    incoming_qty = models.IntegerField(default=0)
    eta_days = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_primary", "warehouse_name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["offer", "warehouse_name"], name="unique_offer_warehouse_name"),
        ]
        indexes = [
            models.Index(fields=["offer", "-is_primary"], name="sellerinv_offer_primary_idx"),
        ]

    def __str__(self):
        return f"Inventory(offer={self.offer_id}, warehouse={self.warehouse_name})"

    @property
    def available_qty(self) -> int:
        return max(0, int(self.stock_qty or 0) - int(self.reserved_qty or 0))


class StockMovement(TimeStampedModel):
    class FieldType(models.TextChoices):
        STOCK = "stock", "Остаток"
        RESERVED = "reserved", "Резерв"
        INCOMING = "incoming", "В пути"

    inventory = models.ForeignKey(SellerInventory, on_delete=models.CASCADE, related_name="movements")
    field_type = models.CharField(max_length=16, choices=FieldType.choices)
    delta = models.IntegerField()
    before_value = models.IntegerField(default=0)
    after_value = models.IntegerField(default=0)
    reason = models.CharField(max_length=255, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["inventory", "-created_at"], name="stockmv_inv_created_idx"),
        ]

    def __str__(self):
        return f"StockMovement(inventory={self.inventory_id}, field={self.field_type}, delta={self.delta})"
