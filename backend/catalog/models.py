from django.db import models
from django.core.validators import RegexValidator
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils.text import slugify
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
    slug = models.SlugField(max_length=160, unique=True, blank=True, db_index=False)
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to='brand_photos/', null=True, blank=True)
    landing_body = models.TextField(blank=True)
    faq_title = models.CharField(max_length=255, blank=True)
    faq_body = models.TextField(blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            if not base or base.isdigit():
                base = f"brand-{self.pk}" if self.pk else "brand"
            candidate = base
            suffix = 2
            while Brand.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{suffix}"
                suffix += 1
            self.slug = candidate
        return super().save(*args, **kwargs)

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
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=False)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children")
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to='category_photos/', null=True, blank=True)
    hero_title = models.CharField(max_length=255, blank=True)
    hero_text = models.TextField(blank=True)
    landing_body = models.TextField(blank=True)
    faq_title = models.CharField(max_length=255, blank=True)
    faq_body = models.TextField(blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            if not base or base.isdigit():
                base = f"category-{self.pk}" if self.pk else "category"
            candidate = base
            suffix = 2
            while Category.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{suffix}"
                suffix += 1
            self.slug = candidate
        return super().save(*args, **kwargs)

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
        # Restrict each product to a maximum of 10 images
        if not self.pk and self.product.images.count() >= 10:
            raise ValidationError("A product may have no more than 10 images.")

    def save(self, *args, **kwargs):
        # Ensure clean() runs during save
        self.full_clean()
        return super().save(*args, **kwargs)


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


class Collection(TimeStampedModel, SeoFieldsMixin):
    name = models.CharField(max_length=160, unique=True)
    slug = models.SlugField(max_length=180, unique=True, blank=True, db_index=False)
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to="collection_photos/", null=True, blank=True)
    hero_title = models.CharField(max_length=200, blank=True)
    hero_text = models.TextField(blank=True)
    landing_body = models.TextField(blank=True)
    faq_title = models.CharField(max_length=255, blank=True)
    faq_body = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    products = models.ManyToManyField(Product, through="CollectionItem", related_name="collections", blank=True)

    class Meta:
        ordering = ["-is_featured", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            if not base or base.isdigit():
                base = f"collection-{self.pk}" if self.pk else "collection"
            candidate = base
            suffix = 2
            while Collection.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{suffix}"
                suffix += 1
            self.slug = candidate
        return super().save(*args, **kwargs)


class CollectionItem(TimeStampedModel):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="collection_items")
    ordering = models.PositiveIntegerField(default=0)
    highlight = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["ordering", "id"]
        constraints = [
            models.UniqueConstraint(fields=["collection", "product"], name="unique_collection_product"),
        ]

    def __str__(self):
        return f"{self.collection_id} · {self.product_id}"


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


class ProductReview(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    text = models.TextField(blank=True, default="")
    is_verified_purchase = models.BooleanField(default=False)
    helpful_count = models.PositiveIntegerField(default=0)
    unhelpful_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "user"], name="unique_product_review_per_user"),
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"Review(product={self.product_id}, user={self.user_id}, rating={self.rating})"


class ProductReviewComment(TimeStampedModel):
    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_review_comments")
    text = models.TextField()

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"ReviewComment(review={self.review_id}, user={self.user_id})"


class ProductReviewPhoto(TimeStampedModel):
    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name="photos")
    image_url = models.URLField()
    caption = models.CharField(max_length=160, blank=True)
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordering", "id"]

    def __str__(self):
        return f"ReviewPhoto(review={self.review_id})"


class ProductReviewVote(TimeStampedModel):
    class Value(models.TextChoices):
        HELPFUL = "helpful", "Helpful"
        UNHELPFUL = "unhelpful", "Unhelpful"

    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_review_votes")
    value = models.CharField(max_length=16, choices=Value.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["review", "user"], name="unique_review_vote_per_user"),
        ]

    def __str__(self):
        return f"ReviewVote(review={self.review_id}, user={self.user_id}, value={self.value})"


class ProductQuestion(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="questions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_questions")
    question_text = models.TextField()
    answer_text = models.TextField(blank=True, default="")
    answered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="answered_product_questions",
    )
    answered_at = models.DateTimeField(null=True, blank=True)
    is_public = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"ProductQuestion(product={self.product_id}, user={self.user_id})"
