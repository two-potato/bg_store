from django.core.management.base import BaseCommand
from decimal import Decimal
from catalog.models import Brand, Series, Category, Product, ProductImage, Country, Color


class Command(BaseCommand):
    help = "Seed minimal catalog data for dev"

    def handle(self, *args, **options):
        brand, _ = Brand.objects.get_or_create(name="BaristaPro")
        series, _ = Series.objects.get_or_create(brand=brand, name="Classic")

        # Countries and colors
        countries = {
            "Италия": ("ITA"),
            "Россия": ("RUS"),
            "Китай": ("CHN"),
        }
        country_objs = {}
        for name, iso in countries.items():
            country_objs[name], _ = Country.objects.get_or_create(name=name, defaults={"iso_code": iso})

        color_names = ["Красный", "Зелёный", "Синий", "Чёрный", "Белый"]
        color_objs = {}
        for cname in color_names:
            color_objs[cname], _ = Color.objects.get_or_create(name=cname)

        # Ensure base categories
        cat_coffee, _ = Category.objects.get_or_create(name="Кофе")
        cat_syrups, _ = Category.objects.get_or_create(name="Сиропы")
        cat_drinks, _ = Category.objects.get_or_create(name="Безалкогольные напитки")
        cat_supplies, _ = Category.objects.get_or_create(name="Расходники для баров")

        categories = [
            (cat_coffee,  "10", "Кофе",        "Италия", "Зёрна"),
            (cat_syrups,  "20", "Сироп",       "Россия", "Сироп"),
            (cat_drinks,  "30", "Напиток",     "Россия", "Жидкость"),
            (cat_supplies,"40", "Расходник",    "Китай",  "Пластик"),
        ]

        created_total = 0
        for cat, prefix, base_name, country, material in categories:
            for i in range(1, 11):
                # 8-digit numeric SKU, e.g., 10000001
                sku = f"{int(prefix):02d}{i:06d}"
                defaults = dict(
                    manufacturer_sku=f"{prefix}M-{i:03d}",
                    name=f"{base_name} #{i}",
                    brand=brand,
                    series=series if cat in (cat_coffee, cat_syrups) else None,
                    category=cat,
                    country_of_origin=country_objs[country],
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
                    # assign a color from the list for demo
                    p.color = color_objs[color_names[i % len(color_names)]]
                    p.save(update_fields=["color"])
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
