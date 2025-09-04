from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from core.models import TimeStampedModel

class SeoFieldsMixin(models.Model):
    """Reusable mixin to add SEO metadata to models."""
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)

    class Meta:
        abstract = True

class Color(TimeStampedModel):
    """Product colour lookup."""
    name = models.CharField(max_length=80, unique=True)
    hex_code = models.CharField(max_length=7, blank=True)

    def __str__(self):
        return self.name

class Country(TimeStampedModel):
    """Country lookup."""
    name = models.CharField(max_length=120, unique=True)
    iso_code = models.CharField(max_length=3, unique=True)

    def __str__(self):
        return self.name

class Brand(TimeStampedModel, SeoFieldsMixin):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to='brand_photos/', null=True, blank=True)

    def __str__(self):
        return self.name

class Series(TimeStampedModel, SeoFieldsMixin):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="series")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to='series_photos/', null=True, blank=True)

    class Meta:
        unique_together = (("brand", "name"),)

    def __str__(self):
        return f"{self.brand} / {self.name}"

class Category(TimeStampedModel, SeoFieldsMixin):
    name = models.CharField(max_length=200)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children")
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to='category_photos/', null=True, blank=True)

    def __str__(self):
        return self.name

class Tag(TimeStampedModel):
    name = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(max_length=64, unique=True)

    def __str__(self):
        return self.name

class Product(TimeStampedModel, SeoFieldsMixin):
    # артикул должен состоять из 8 цифр
    sku = models.CharField(
        max_length=8,
        unique=True,
        validators=[RegexValidator(regex=r'^\d{8}$', message="SKU must be exactly 8 digits.")],
        help_text="8-digit product code",
    )
    manufacturer_sku = models.CharField(max_length=64, blank=True)
    name = models.CharField(max_length=255)
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
    is_new = models.BooleanField(default=False)
    is_promo = models.BooleanField(default=False)
    attributes = models.JSONField(default=dict, blank=True)
    composition = models.TextField(blank=True)
    shelf_life = models.CharField(max_length=120, blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="products")

    def __str__(self):
        return f"{self.sku} — {self.name}"

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
        # Restrict each product to a maximum of 10 images
        if not self.pk and self.product.images.count() >= 10:
            raise ValidationError("A product may have no more than 10 images.")

    def save(self, *args, **kwargs):
        # Ensure clean() runs during save
        self.full_clean()
        return super().save(*args, **kwargs)
