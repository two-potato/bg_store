from django.core.management.base import BaseCommand
from decimal import Decimal
import random
from catalog.models import Brand, Series, Category, Product, ProductImage, Country, Color, Tag
from django.utils.text import slugify


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
            (cat_syrups,  "20", "Сироп",       "Россия", "Жидкость"),
            (cat_drinks,  "30", "Напиток",     "Россия", "Жидкость"),
            (cat_supplies,"40", "Расходник",    "Китай",  "Пластик"),
        ]

        created_total = 0
        for cat, prefix, base_name, country, material in categories:
            for i in range(1, 11):
                # 8-digit numeric SKU, e.g., 10000001
                sku = f"{int(prefix):02d}{i:06d}"
                # Simple heuristic fields per category
                is_promo = (i % 5 == 0)
                unit = (
                    "пач." if cat == cat_coffee else
                    ("бут." if cat in (cat_syrups, cat_drinks) else "шт")
                )
                flavor = "Ваниль" if cat == cat_syrups else ("Яблоко" if cat == cat_drinks else "")
                composition = (
                    "100% арабика" if cat == cat_coffee else (
                        "Сахар, вода, ароматизатор" if cat == cat_syrups else "Состав по ГОСТ"
                    )
                )
                shelf_life = "12 месяцев"
                description = (
                    f"{base_name} #{i} от {brand.name} — практичный товар для ежедневной работы и стабильной выдачи. "
                    f"Позиция относится к категории «{cat.name}», удобно хранится и быстро используется в смене.\n\n"
                    f"Подробности: состав — {composition}. "
                    f"Срок годности — {shelf_life}. "
                    "Рекомендуется хранить в сухом месте, вдали от прямых солнечных лучей, "
                    "и использовать в рамках стандартных технологических карт."
                )

                defaults = dict(
                    manufacturer_sku=f"{prefix}M-{i:03d}",
                    name=f"{base_name} #{i}",
                    brand=brand,
                    series=series if cat in (cat_coffee, cat_syrups) else None,
                    category=cat,
                    country_of_origin=country_objs[country],
                    material=material,
                    purpose=f"{base_name} — демо позиция",
                    unit=unit,
                    barcode=f"000000000{i:09d}",
                    price=Decimal(100 + i * 10),
                    stock_qty=100 - i,
                    is_new=(i <= 3),
                    is_promo=is_promo,
                    attributes={},
                    flavor=flavor,
                    composition=composition,
                    shelf_life=shelf_life,
                    description=description,
                )
                p, created = Product.objects.get_or_create(sku=sku, defaults=defaults)
                # enrich physical properties randomly for demo
                try:
                    if cat == cat_coffee:
                        p.weight_g = random.choice([250, 500, 1000])
                        p.pack_qty = 1
                        p.diameter_mm = None
                        p.height_mm = random.choice([120, 150, 200])
                        p.length_mm = random.choice([80, 100, 120])
                        p.width_mm = random.choice([60, 80, 100])
                        p.volume_ml = None
                    elif cat in (cat_syrups, cat_drinks):
                        p.volume_ml = random.choice([500, 700, 1000])
                        p.weight_g = random.choice([900, 1200, 1500])
                        p.height_mm = random.choice([240, 260, 280])
                        p.diameter_mm = random.choice([65, 70, 75])
                        p.length_mm = None
                        p.width_mm = None
                    else:
                        p.weight_g = random.choice([50, 100, 200])
                        p.length_mm = random.choice([100, 150, 200])
                        p.width_mm = random.choice([50, 80, 120])
                        p.height_mm = random.choice([20, 40, 60])
                        p.volume_ml = None
                except Exception:
                    pass

                if created:
                    # assign a color from the list for demo
                    p.color = color_objs[color_names[i % len(color_names)]]
                    # ensure we persist updated random props too
                    p.save()
                else:
                    if not (p.description or "").strip():
                        p.description = description
                        p.save(update_fields=["description"])
                    p.save()
                # Ensure minimum 3 photos for each product
                img_count = p.images.count()
                if img_count < 3:
                    for idx in range(img_count, 3):
                        seed = f"{prefix.lower()}-{i}-{idx + 1}"
                        ProductImage.objects.create(
                            product=p,
                            url=f"https://picsum.photos/seed/{seed}/600/400",
                            alt=p.name,
                            is_primary=(idx == 0 and img_count == 0),
                            ordering=idx,
                        )
                created_total += int(created)

                # Ensure tags (brand, category, flags, sku prefix, country, color, flavor)
                tag_objs = []
                def ensure_tag(name: str, slug: str):
                    t, _ = Tag.objects.get_or_create(slug=slug, defaults={"name": name})
                    tag_objs.append(t)

                if p.brand:
                    ensure_tag(p.brand.name, f"brand-{slugify(p.brand.name)}")
                if p.category:
                    ensure_tag(p.category.name, f"cat-{slugify(p.category.name)}")
                if p.country_of_origin:
                    ensure_tag(p.country_of_origin.name, f"country-{slugify(p.country_of_origin.name)}")
                # flags
                if p.is_new:
                    ensure_tag("Новинка", "flag-new")
                if p.is_promo:
                    ensure_tag("Акция", "flag-promo")
                # sku prefix
                ensure_tag(base_name, f"sku-{slugify(base_name)}")
                # color
                if p.color:
                    ensure_tag(p.color.name, f"color-{slugify(p.color.name)}")
                # flavor
                if p.flavor:
                    ensure_tag(p.flavor, f"flavor-{slugify(p.flavor)}")
                # Fallbacks to guarantee minimum tag count for every product
                fallback_tags = [
                    ("Товар", "type-product"),
                    ("Каталог", "type-catalog"),
                    (f"SKU {p.sku[:2]}", f"sku-prefix-{slugify(p.sku[:2])}"),
                    ("Ассортимент", "type-assortment"),
                ]
                for name, slug in fallback_tags:
                    if len({t.id for t in tag_objs}) >= 4:
                        break
                    ensure_tag(name, slug)
                if tag_objs:
                    for t in tag_objs:
                        if not p.tags.filter(id=t.id).exists():
                            p.tags.add(t)

        self.stdout.write(self.style.SUCCESS(f"Seeded catalog data. New products created: {created_total}"))
