from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.text import slugify

from core.models import TimeStampedModel

from .mixins import SeoFieldsMixin, normalize_public_media_url
from .taxonomy import Brand, Category, Color, Country, Series, Tag


class Product(TimeStampedModel, SeoFieldsMixin):
    class PublicationStatus(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PUBLISHED = "published", "Опубликован"
        ARCHIVED = "archived", "Архив"

    sku = models.CharField(
        max_length=8,
        unique=True,
        validators=[RegexValidator(regex=r"^\d{8}$", message="SKU must be exactly 8 digits.")],
        help_text="8-digit product code",
    )
    manufacturer_sku = models.CharField(max_length=64, blank=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=False)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, related_name="products")
    series = models.ForeignKey(Series, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name="products")
    country_of_origin = models.ForeignKey(Country, null=True, blank=True, on_delete=models.SET_NULL)
    material = models.CharField(max_length=120, blank=True)
    purpose = models.CharField(max_length=255, blank=True)
    color = models.ForeignKey(Color, null=True, blank=True, on_delete=models.SET_NULL)
    flavor = models.CharField(max_length=120, blank=True)
    diameter_mm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    height_mm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    length_mm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    width_mm = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    volume_ml = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    weight_g = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    pack_qty = models.IntegerField(default=1)
    unit = models.CharField(max_length=16, default="шт")
    barcode = models.CharField(max_length=64, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_qty = models.IntegerField(default=0)
    min_order_qty = models.PositiveIntegerField(default=1)
    lead_time_days = models.PositiveIntegerField(default=0)
    is_new = models.BooleanField(default=False)
    is_promo = models.BooleanField(default=False)
    publication_status = models.CharField(max_length=16, choices=PublicationStatus.choices, default=PublicationStatus.PUBLISHED)
    attributes = models.JSONField(default=dict, blank=True)
    composition = models.TextField(blank=True)
    shelf_life = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="products")
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marketplace_products",
    )

    class Meta:
        indexes = [
            models.Index(fields=["-is_new", "name", "id"], name="product_new_name_idx"),
            models.Index(fields=["-is_promo", "name", "id"], name="product_promo_name_idx"),
            models.Index(fields=["price", "name", "id"], name="product_price_name_idx"),
            models.Index(fields=["category", "-is_new", "name", "id"], name="product_cat_new_idx"),
            models.Index(fields=["brand", "-is_new", "name", "id"], name="product_brand_new_idx"),
            models.Index(fields=["seller", "-is_new", "name", "id"], name="product_seller_new_idx"),
            models.Index(fields=["seller", "publication_status", "-updated_at"], name="product_seller_pub_upd_idx"),
        ]

    def __str__(self):
        return f"{self.sku} — {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            if not base or base.isdigit():
                base = f"product-{self.pk}" if self.pk else "product"
            candidate = base
            suffix = 2
            while Product.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{suffix}"
                suffix += 1
            self.slug = candidate
        return super().save(*args, **kwargs)

    @property
    def display_price(self):
        return getattr(self, "_effective_price", self.price)

    @property
    def display_stock_qty(self):
        return getattr(self, "_effective_stock_qty", self.stock_qty)

    @property
    def display_lead_time_days(self):
        return getattr(self, "_effective_lead_time_days", self.lead_time_days)

    @property
    def display_min_order_qty(self):
        return getattr(self, "_effective_min_order_qty", self.min_order_qty)

    @property
    def active_offer(self):
        return getattr(self, "_active_offer", None)


class ProductImage(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    url = models.URLField()
    alt = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordering", "id"]

    def clean(self):
        super().clean()
        if not self.pk and self.product.images.count() >= 10:
            raise ValidationError("A product may have no more than 10 images.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def public_url(self) -> str:
        return normalize_public_media_url(self.url)


class ProductDocument(TimeStampedModel):
    class Kind(models.TextChoices):
        CERTIFICATE = "certificate", "Сертификат"
        SPEC = "spec", "Спецификация"
        PDF = "pdf", "PDF"
        OTHER = "other", "Прочее"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=255)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.PDF)
    file_url = models.URLField()
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordering", "id"]

    def __str__(self):
        return f"{self.product_id} · {self.title}"
