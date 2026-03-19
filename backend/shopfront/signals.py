from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from catalog.models import Brand, Category, Product, ProductImage, ProductReview, Tag


def _invalidate(*keys: str):
    cache.delete_many(list(keys))


@receiver([post_save, post_delete], sender=Category)
def _invalidate_categories_cache(**kwargs):
    _invalidate(
        "shopfront:header_categories:v1",
        "shopfront:home:category_ids:v1:8",
        "shopfront:catalog:categories:v1",
    )


@receiver([post_save, post_delete], sender=Brand)
def _invalidate_brands_cache(**kwargs):
    _invalidate("shopfront:catalog:brands:v1")


@receiver([post_save, post_delete], sender=Tag)
def _invalidate_tags_cache(**kwargs):
    _invalidate("shopfront:catalog:tags:v1")


@receiver([post_save, post_delete], sender=Product)
@receiver([post_save, post_delete], sender=ProductImage)
def _invalidate_products_cache(**kwargs):
    _invalidate("shopfront:home:product_ids:v1:12")


@receiver([post_save, post_delete], sender=ProductReview)
def _invalidate_product_review_cache(sender, instance: ProductReview, **kwargs):
    keys = [
        "shopfront:home:product_ids:v1:12",
        f"shopfront:product_rating:v1:{instance.product_id}",
    ]
    if instance.product.seller_id:
        keys.append(f"shopfront:seller_rating:v1:{instance.product.seller_id}")
    _invalidate(*keys)
