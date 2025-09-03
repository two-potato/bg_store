from django.core.management.base import BaseCommand
from decimal import Decimal
from catalog.models import Brand, Series, Category, Product, ProductImage


class Command(BaseCommand):
    help = "Seed minimal catalog data for dev"

    def handle(self, *args, **options):
        brand, _ = Brand.objects.get_or_create(name="BaristaPro")
        series, _ = Series.objects.get_or_create(brand=brand, name="Classic")

        # Ensure base categories
        cat_coffee, _ = Category.objects.get_or_create(name="Кофе")
        cat_syrups, _ = Category.objects.get_or_create(name="Сиропы")
        cat_drinks, _ = Category.objects.get_or_create(name="Безалкогольные напитки")
        cat_supplies, _ = Category.objects.get_or_create(name="Расходники для баров")

        categories = [
            (cat_coffee,  "COF", "Кофе",        "Италия", "Зёрна"),
            (cat_syrups,  "SYR", "Сироп",       "Россия", "Сироп"),
            (cat_drinks,  "DRK", "Напиток",     "Россия", "Жидкость"),
            (cat_supplies,"SUP", "Расходник",    "Китай",  "Пластик"),
        ]

        created_total = 0
        for cat, prefix, base_name, country, material in categories:
            for i in range(1, 11):
                sku = f"{prefix}-{i:03d}"
                defaults = dict(
                    manufacturer_sku=f"{prefix}M-{i:03d}",
                    name=f"{base_name} #{i}",
                    brand=brand,
                    series=series if prefix in ("COF", "SYR") else None,
                    category=cat,
                    country_of_origin=country,
                    material=material,
                    purpose=f"{base_name} — демо позиция",
                    unit="шт" if prefix == "SUP" else ("бут." if prefix in ("SYR","DRK") else "уп."),
                    barcode=f"000000000{i:09d}",
                    price=Decimal(100 + i * 10),
                    stock_qty=100 - i,
                    is_new=(i <= 3),
                    attributes={},
                )
                p, created = Product.objects.get_or_create(sku=sku, defaults=defaults)
                if created:
                    seed = f"{prefix.lower()}-{i}"
                    ProductImage.objects.create(
                        product=p,
                        url=f"https://picsum.photos/seed/{seed}/600/400",
                        alt=p.name,
                        is_primary=True,
                        ordering=0,
                    )
                    created_total += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded catalog data. New products created: {created_total}"))
