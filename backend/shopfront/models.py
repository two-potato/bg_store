from django.conf import settings
from django.db import models

from catalog.models import Product
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
