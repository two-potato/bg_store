"""Catalog signals for search maintenance and catalog-owned cache invalidation."""

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from catalog.models import Brand, Category, Product, ProductImage, ProductReview, Tag
from catalog.tasks import delete_product_from_search, upsert_product_in_search


def _invalidate(*keys: str) -> None:
    cache.delete_many(list(keys))


def _invalidate_product_list_cache() -> None:
    _invalidate("shopfront:home:product_ids:v1:12")


@receiver(post_save, sender=Product)
def product_post_save(sender, instance: Product, **kwargs) -> None:
    """Invalidate product caches and schedule an OpenSearch upsert after commit."""
    _invalidate_product_list_cache()
    transaction.on_commit(lambda: upsert_product_in_search.delay(product_id=instance.id))


@receiver(post_delete, sender=Product)
def product_post_delete(sender, instance: Product, **kwargs) -> None:
    """Invalidate product caches and schedule an OpenSearch delete after commit."""
    _invalidate_product_list_cache()
    transaction.on_commit(lambda: delete_product_from_search.delay(product_id=instance.id))


@receiver([post_save, post_delete], sender=Category)
def invalidate_category_caches(**kwargs) -> None:
    _invalidate(
        "shopfront:header_categories:v1",
        "shopfront:home:category_ids:v1:8",
        "shopfront:catalog:categories:v1",
    )


@receiver([post_save, post_delete], sender=Brand)
def invalidate_brand_caches(**kwargs) -> None:
    _invalidate("shopfront:catalog:brands:v1")


@receiver([post_save, post_delete], sender=Tag)
def invalidate_tag_caches(**kwargs) -> None:
    _invalidate("shopfront:catalog:tags:v1")


@receiver([post_save, post_delete], sender=ProductImage)
def invalidate_product_image_caches(**kwargs) -> None:
    _invalidate_product_list_cache()


@receiver([post_save, post_delete], sender=ProductReview)
def invalidate_product_review_caches(sender, instance: ProductReview, **kwargs) -> None:
    keys = [
        "shopfront:home:product_ids:v1:12",
        f"shopfront:product_rating:v1:{instance.product_id}",
    ]
    if instance.product.seller_id:
        keys.append(f"shopfront:seller_rating:v1:{instance.product.seller_id}")
    _invalidate(*keys)
