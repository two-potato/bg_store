"""Asynchronous catalog maintenance tasks."""

from __future__ import annotations

import logging

from celery import shared_task

from catalog.models import Product
from catalog.opensearch_index import delete_product, upsert_product

log = logging.getLogger("catalog")


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def upsert_product_in_search(self, product_id: int) -> None:
    """Reindex a single product in OpenSearch by id."""
    product = (
        Product.objects.select_related("brand", "category", "country_of_origin", "seller", "seller__seller_store")
        .prefetch_related("tags")
        .filter(pk=product_id)
        .first()
    )
    if product is None:
        log.info("opensearch_upsert_skip_missing_product", extra={"product_id": product_id})
        return
    upsert_product(product)


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def delete_product_from_search(self, product_id: int) -> None:
    """Delete a single product document from OpenSearch by id."""
    delete_product(product_id)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def reindex_products_for_seller(self, seller_id: int) -> int:
    """Reindex all products belonging to a given seller."""
    product_ids = list(Product.objects.filter(seller_id=seller_id).values_list("id", flat=True))
    for product_id in product_ids:
        upsert_product_in_search.delay(product_id=product_id)
    log.info("seller_products_reindex_scheduled", extra={"seller_id": seller_id, "count": len(product_ids)})
    return len(product_ids)
