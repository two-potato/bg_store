import json

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

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
                "analysis": {
                    "normalizer": {
                        "folding_normalizer": {
                            "type": "custom",
                            "char_filter": [],
                            "filter": ["lowercase", "asciifolding"],
                        }
                    }
                }
            },
            "mappings": {
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "text"},
                    "sku": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "normalizer": "folding_normalizer",
                            }
                        },
                    },
                    "brand": {"type": "text"},
                    "category": {"type": "text"},
                    "country_of_origin": {"type": "text"},
                    "description": {"type": "text"},
                    "price": {"type": "double"},
                    "is_new": {"type": "boolean"},
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

        qs = Product.objects.select_related("brand", "category", "country_of_origin").all().order_by("id")
        bulk_lines = []
        count = 0
        for p in qs.iterator(chunk_size=500):
            bulk_lines.append(json.dumps({"index": {"_index": index, "_id": p.id}}))
            bulk_lines.append(
                json.dumps(
                    {
                        "id": p.id,
                        "name": p.name,
                        "sku": p.sku,
                        "brand": p.brand.name if p.brand else "",
                        "category": p.category.name if p.category else "",
                        "country_of_origin": p.country_of_origin.name if p.country_of_origin else "",
                        "description": p.description or "",
                        "price": float(p.price or 0),
                        "is_new": bool(p.is_new),
                    },
                    ensure_ascii=False,
                )
            )
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
