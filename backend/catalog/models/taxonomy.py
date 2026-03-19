from django.db import models
from django.utils.text import slugify

from core.models import TimeStampedModel

from .mixins import SeoFieldsMixin


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
    photo = models.ImageField(upload_to="brand_photos/", null=True, blank=True)
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
    photo = models.ImageField(upload_to="series_photos/", null=True, blank=True)

    class Meta:
        unique_together = (("brand", "name"),)

    def __str__(self):
        return f"{self.brand} / {self.name}"


class Category(TimeStampedModel, SeoFieldsMixin):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=False)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children")
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to="category_photos/", null=True, blank=True)
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
