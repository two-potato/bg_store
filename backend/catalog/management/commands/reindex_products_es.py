import json

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from catalog.es_index import product_doc
from catalog.models import Product


class Command(BaseCommand):
    help = "Rebuild Elasticsearch index for products used by live search"

    def handle(self, *args, **options):
        es_url = settings.ES_URL.rstrip("/")
        index = settings.ES_PRODUCTS_INDEX
        timeout = settings.ES_TIMEOUT_SECONDS
        index_url = f"{es_url}/{index}"

        mappings = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {
                    "normalizer": {
                        "folding_normalizer": {
                            "type": "custom",
                            "char_filter": [],
                            "filter": ["lowercase", "asciifolding"],
                        }
                    },
                    "analyzer": {
                        "folding_text": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": ["lowercase", "asciifolding"],
                        }
                    },
                }
            },
            "mappings": {
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "text", "analyzer": "folding_text"},
                    "sku": {
                        "type": "text",
                        "analyzer": "folding_text",
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "normalizer": "folding_normalizer",
                            }
                        },
                    },
                    "manufacturer_sku": {
                        "type": "text",
                        "analyzer": "folding_text",
                        "fields": {"keyword": {"type": "keyword", "normalizer": "folding_normalizer"}},
                    },
                    "barcode": {
                        "type": "text",
                        "analyzer": "folding_text",
                        "fields": {"keyword": {"type": "keyword", "normalizer": "folding_normalizer"}},
                    },
                    "brand": {"type": "text", "analyzer": "folding_text"},
                    "series": {"type": "text", "analyzer": "folding_text"},
                    "category": {"type": "text", "analyzer": "folding_text"},
                    "country_of_origin": {
                        "type": "text",
                        "analyzer": "folding_text",
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                            }
                        },
                    },
                    "country_of_origin_keyword": {
                        "type": "keyword",
                        "normalizer": "folding_normalizer",
                    },
                    "store_name": {"type": "text", "analyzer": "folding_text"},
                    "store_description": {"type": "text", "analyzer": "folding_text"},
                    "seller_username": {"type": "text", "analyzer": "folding_text"},
                    "material": {"type": "text", "analyzer": "folding_text"},
                    "purpose": {"type": "text", "analyzer": "folding_text"},
                    "flavor": {"type": "text", "analyzer": "folding_text"},
                    "tags": {"type": "text", "analyzer": "folding_text"},
                    "description": {"type": "text", "analyzer": "folding_text"},
                    "price": {"type": "double"},
                    "is_new": {"type": "boolean"},
                    "is_promo": {"type": "boolean"},
                    "in_stock": {"type": "boolean"},
                    "search_terms": {"type": "keyword", "normalizer": "folding_normalizer"},
                    "suggest": {"type": "completion", "analyzer": "folding_text"},
                }
            },
        }

        self.stdout.write("Deleting old index (if exists)...")
        try:
            requests.delete(index_url, timeout=timeout)
        except Exception:
            pass

        self.stdout.write("Creating index...")
        resp = requests.put(index_url, json=mappings, timeout=timeout)
        if resp.status_code >= 300:
            raise RuntimeError(f"Failed to create index: {resp.status_code} {resp.text}")

        qs = Product.objects.select_related(
            "brand", "category", "country_of_origin", "seller", "seller__seller_store"
        ).prefetch_related("tags").all().order_by("id")
        bulk_lines = []
        count = 0
        for p in qs.iterator(chunk_size=500):
            bulk_lines.append(json.dumps({"index": {"_index": index, "_id": p.id}}))
            bulk_lines.append(json.dumps(product_doc(p), ensure_ascii=False))
            count += 1

            if len(bulk_lines) >= 1000:
                payload = "\n".join(bulk_lines) + "\n"
                r = requests.post(
                    f"{es_url}/_bulk",
                    data=payload.encode("utf-8"),
                    headers={"Content-Type": "application/x-ndjson"},
                    timeout=max(timeout, 5),
                )
                r.raise_for_status()
                bulk_lines = []

        if bulk_lines:
            payload = "\n".join(bulk_lines) + "\n"
            r = requests.post(
                f"{es_url}/_bulk",
                data=payload.encode("utf-8"),
                headers={"Content-Type": "application/x-ndjson"},
                timeout=max(timeout, 5),
            )
            r.raise_for_status()

        refresh = requests.post(f"{index_url}/_refresh", timeout=timeout)
        refresh.raise_for_status()

        self.stdout.write(self.style.SUCCESS(f"Indexed products: {count}"))
