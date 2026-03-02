from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from catalog.es_index import delete_product, upsert_product
from catalog.models import Product


@receiver(post_save, sender=Product)
def product_post_save(sender, instance, **kwargs):
    upsert_product(instance)


@receiver(post_delete, sender=Product)
def product_post_delete(sender, instance, **kwargs):
    delete_product(instance.id)
