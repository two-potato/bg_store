"""Catalog signals that schedule asynchronous search index maintenance."""

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from catalog.models import Product
from catalog.tasks import delete_product_from_search, upsert_product_in_search


@receiver(post_save, sender=Product)
def product_post_save(sender, instance: Product, **kwargs) -> None:
    """Schedule a product upsert in OpenSearch after the transaction commits."""
    transaction.on_commit(lambda: upsert_product_in_search.delay(product_id=instance.id))


@receiver(post_delete, sender=Product)
def product_post_delete(sender, instance: Product, **kwargs) -> None:
    """Schedule a product delete in OpenSearch after the transaction commits."""
    transaction.on_commit(lambda: delete_product_from_search.delay(product_id=instance.id))
