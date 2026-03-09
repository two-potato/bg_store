from django.conf import settings
from django.db import models

from uuid import uuid4

from catalog.models import Product, Brand, Category
from core.models import TimeStampedModel


class FavoriteProduct(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorite_products",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="favorited_by",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="unique_favorite_product_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="fav_user_created_idx"),
        ]

    def __str__(self) -> str:
        return f"Favorite(user={self.user_id}, product={self.product_id})"


class SavedSearch(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_searches",
    )
    name = models.CharField(max_length=120)
    querystring = models.CharField(max_length=512)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="saved_search_user_created_idx"),
        ]

    def __str__(self) -> str:
        return f"SavedSearch(user={self.user_id}, name={self.name})"


class PersistentCart(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="persistent_cart",
    )
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Persistent cart"
        verbose_name_plural = "Persistent carts"

    def __str__(self) -> str:
        return f"PersistentCart(user={self.user_id})"


class CategorySubscription(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="category_subscriptions",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="subscribers",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "category"],
                name="unique_category_subscription_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="cat_sub_user_created_idx"),
        ]

    def __str__(self) -> str:
        return f"CategorySubscription(user={self.user_id}, category={self.category_id})"


class BrandSubscription(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="brand_subscriptions",
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE,
        related_name="subscribers",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "brand"],
                name="unique_brand_subscription_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="brand_sub_user_created_idx"),
        ]

    def __str__(self) -> str:
        return f"BrandSubscription(user={self.user_id}, brand={self.brand_id})"


class RecentlyViewedProduct(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recently_viewed_products",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="recently_viewed_by",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="unique_recently_viewed_product_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-updated_at"], name="recent_view_user_updated_idx"),
        ]

    def __str__(self) -> str:
        return f"RecentlyViewed(user={self.user_id}, product={self.product_id})"


class SavedList(TimeStampedModel):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        FAVORITES = "favorites", "Favorites"
        ORDER = "order", "Order"
        CART = "cart", "Cart"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_lists",
    )
    name = models.CharField(max_length=140)
    description = models.CharField(max_length=255, blank=True)
    share_token = models.CharField(max_length=40, unique=True, blank=True, db_index=True)
    is_public = models.BooleanField(default=False)
    source = models.CharField(max_length=24, choices=Source.choices, default=Source.MANUAL)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["user", "-updated_at"], name="saved_list_user_updated_idx"),
        ]

    def __str__(self) -> str:
        return f"SavedList(user={self.user_id}, name={self.name})"

    def ensure_share_token(self) -> str:
        if self.share_token:
            return self.share_token
        self.share_token = uuid4().hex
        return self.share_token

    def save(self, *args, **kwargs):
        if not self.share_token:
            self.ensure_share_token()
        return super().save(*args, **kwargs)


class SavedListItem(TimeStampedModel):
    saved_list = models.ForeignKey(
        SavedList,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="saved_list_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    note = models.CharField(max_length=180, blank=True)
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordering", "-updated_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["saved_list", "product"],
                name="unique_saved_list_product",
            ),
        ]

    def __str__(self) -> str:
        return f"SavedListItem(list={self.saved_list_id}, product={self.product_id})"
