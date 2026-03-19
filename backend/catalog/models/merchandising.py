from django.db import models
from django.utils.text import slugify

from core.models import TimeStampedModel

from .mixins import SeoFieldsMixin
from .product import Product


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
