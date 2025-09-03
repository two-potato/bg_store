from django.db import models
from core.models import TimeStampedModel

class Brand(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    def __str__(self): return self.name

class Series(TimeStampedModel):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="series")
    name = models.CharField(max_length=120)
    class Meta: unique_together = (("brand","name"),)
    def __str__(self): return f"{self.brand} / {self.name}"

class Category(TimeStampedModel):
    name = models.CharField(max_length=200)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children")
    def __str__(self): return self.name

class Tag(TimeStampedModel):
    name = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(max_length=64, unique=True)
    def __str__(self): return self.name

class Product(TimeStampedModel):
    sku = models.CharField(max_length=64, unique=True)                 # наш артикул
    manufacturer_sku = models.CharField(max_length=64, blank=True)     # артикул производителя
    name = models.CharField(max_length=255)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, related_name="products")
    series = models.ForeignKey(Series, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name="products")

    country_of_origin = models.CharField(max_length=120, blank=True)
    material = models.CharField(max_length=120, blank=True)
    purpose = models.CharField(max_length=255, blank=True)
    color = models.CharField(max_length=80, blank=True)
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

    def __str__(self): return f"{self.sku} — {self.name}"

class ProductImage(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    url = models.URLField()
    alt = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    ordering = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["ordering","id"]
