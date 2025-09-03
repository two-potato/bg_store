from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Product, ProductImage, Brand, Category
from .scrape_restinternational import (
    list_1883, list_tinctura, parse_product, upsert_product,
)


ALLOWED_BRANDS = ["1883 Maison Routin", "Tinctura Anima"]
ALLOWED_CATEGORIES = ["Сиропы", "Пюре", "Безалкогольные спириты", "Кордиалы"]


class Command(BaseCommand):
    help = "Reset catalog to only two brands (1883, Tinctura) and four categories, then import from restinternational.ru"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10, help="Items per category")

    @transaction.atomic
    def handle(self, *args, **opts):
        limit = int(opts["limit"]) or 10

        # 1) Wipe products and images
        self.stdout.write("Deleting existing products and images…")
        ProductImage.objects.all().delete()
        Product.objects.all().delete()

        # 2) Keep only allowed brands
        self.stdout.write("Resetting brands…")
        Brand.objects.exclude(name__in=ALLOWED_BRANDS).delete()
        for b in ALLOWED_BRANDS:
            Brand.objects.get_or_create(name=b)

        # 3) Reset categories to allowed set only
        self.stdout.write("Resetting categories…")
        Category.objects.all().delete()
        for c in ALLOWED_CATEGORIES:
            Category.objects.get_or_create(name=c, parent=None)

        imported = 0

        # 4) Import 1883 (siropy -> Сиропы, pyure -> Пюре)
        for slug, cat_name in (("siropy", "Сиропы"), ("pyure", "Пюре")):
            items = list_1883(slug, limit)
            self.stdout.write(self.style.NOTICE(f"1883/{slug}: {len(items)} items"))
            for it in items:
                try:
                    data = parse_product(it["url"]) or {}
                    if not data:
                        continue
                    upsert_product(
                        data,
                        brand_name="1883 Maison Routin",
                        parent_brand_as_category=False,
                        subcategory_name=None,
                        stock_qty=it.get("stock"),
                        sku_prefix="1883-",
                        category_name=cat_name,
                    )
                    imported += 1
                except Exception as e:
                    self.stderr.write(self.style.WARNING(f"Skip 1883: {e}"))

        # 5) Import Tinctura (cordials, non-alcoholic spirits)
        t_items = list_tinctura(limit)
        self.stdout.write(self.style.NOTICE(f"Tinctura items discovered: {len(t_items)}"))
        per_cat = {"Кордиалы": 0, "Безалкогольные спириты": 0}
        for it in t_items:
            try:
                data = parse_product(it["url"]) or {}
                if not data:
                    continue
                if not data.get("brand", "").lower().startswith("tinctura"):
                    continue
                cat_name = "Кордиалы" if "/kordial/" in it["url"] else "Безалкогольные спириты"
                if per_cat[cat_name] >= limit:
                    continue
                upsert_product(
                    data,
                    brand_name="Tinctura Anima",
                    parent_brand_as_category=False,
                    subcategory_name=None,
                    stock_qty=it.get("stock"),
                    sku_prefix="TINCT-",
                    category_name=cat_name,
                )
                per_cat[cat_name] += 1
                imported += 1
            except Exception as e:
                self.stderr.write(self.style.WARNING(f"Skip Tinctura: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Imported: {imported} items"))

