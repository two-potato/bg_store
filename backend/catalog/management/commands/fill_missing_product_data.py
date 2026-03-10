from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils.text import slugify

from catalog.models import Color, Country, Product, Series


class Command(BaseCommand):
    help = "Fill missing non-SEO product fields with deterministic demo defaults"

    def _ensure_country(self, product: Product) -> Country:
        if product.country_of_origin_id:
            return product.country_of_origin
        defaults = {
            "Кофе": ("Италия", "ITA"),
            "Сиропы": ("Россия", "RUS"),
            "Безалкогольные напитки": ("Россия", "RUS"),
            "Расходники для баров": ("Китай", "CHN"),
        }
        cat_name = product.category.name if product.category_id else ""
        name, iso = defaults.get(cat_name, ("Россия", "RUS"))
        country, _ = Country.objects.get_or_create(name=name, defaults={"iso_code": iso})
        return country

    def _ensure_color(self, product: Product) -> Color:
        if product.color_id:
            return product.color
        palette = ["Мятный", "Графит", "Белый", "Черный"]
        idx = (product.id or 1) % len(palette)
        color, _ = Color.objects.get_or_create(name=palette[idx])
        return color

    def _ensure_series(self, product: Product) -> Series | None:
        if product.series_id or not product.brand_id:
            return product.series
        series = product.brand.series.order_by("id").first()
        if series:
            return series
        return Series.objects.create(brand=product.brand, name="Base")

    def _default_texts(self, product: Product) -> dict[str, str]:
        cat = product.category.name.lower() if product.category_id else "товары"
        title = product.name.strip() if product.name else f"Товар {product.sku}"
        flavor = "нейтральный"
        if "сироп" in cat:
            flavor = "ваниль"
        elif "коф" in cat:
            flavor = "классический"
        elif "напит" in cat:
            flavor = "цитрус"

        composition = (
            "Подготовленная вода, натуральные экстракты и пищевые ингредиенты в безопасной концентрации."
            if ("сироп" in cat or "напит" in cat)
            else "Сырье пищевого или технического назначения по отраслевому стандарту."
        )

        p1 = (
            f"{title} предназначен для ежедневного использования в сегменте HoReCa и розничных продаж. "
            "Продукт стабилен в хранении, подходит для типовых технологических карт и предсказуем в работе."
        )
        p2 = (
            "Рекомендовано хранить в сухом месте при комнатной температуре, избегать прямых солнечных лучей. "
            "После вскрытия использовать в сроки, указанные на упаковке производителя."
        )

        return {
            "flavor": flavor,
            "composition": composition,
            "shelf_life": "12 месяцев",
            "purpose": f"Для категории: {product.category.name if product.category_id else 'Каталог'}",
            "material": "Пищевой пластик" if "расход" in cat else "Пищевое сырье",
            "description": f"{p1}\n\n{p2}",
        }

    def _fill_numeric(self, product: Product, updates: dict[str, Any]) -> None:
        cat = product.category.name.lower() if product.category_id else ""

        if product.pack_qty in (None, 0):
            updates["pack_qty"] = 1
        if not product.unit:
            updates["unit"] = "шт"

        if product.price is None or product.price <= 0:
            updates["price"] = Decimal("490.00")
        if product.stock_qty is None or product.stock_qty < 0:
            updates["stock_qty"] = 50

        if product.weight_g is None:
            updates["weight_g"] = Decimal("1000") if "сироп" in cat else Decimal("500")

        if "сироп" in cat or "напит" in cat:
            if product.volume_ml is None:
                updates["volume_ml"] = Decimal("1000")
            if product.height_mm is None:
                updates["height_mm"] = Decimal("280")
            if product.diameter_mm is None:
                updates["diameter_mm"] = Decimal("75")
        else:
            if product.length_mm is None:
                updates["length_mm"] = Decimal("120")
            if product.width_mm is None:
                updates["width_mm"] = Decimal("80")
            if product.height_mm is None:
                updates["height_mm"] = Decimal("60")

    def handle(self, *args, **options):
        candidates = Product.objects.filter(
            Q(manufacturer_sku__isnull=True) | Q(manufacturer_sku="") |
            Q(material__isnull=True) | Q(material="") |
            Q(purpose__isnull=True) | Q(purpose="") |
            Q(flavor__isnull=True) | Q(flavor="") |
            Q(composition__isnull=True) | Q(composition="") |
            Q(shelf_life__isnull=True) | Q(shelf_life="") |
            Q(description__isnull=True) | Q(description="") |
            Q(barcode__isnull=True) | Q(barcode="") |
            Q(country_of_origin__isnull=True) |
            Q(color__isnull=True) |
            Q(series__isnull=True)
        ).select_related("brand", "category", "country_of_origin", "color", "series")

        updated_count = 0

        for p in candidates.iterator():
            updates: dict[str, Any] = {}
            texts = self._default_texts(p)

            if not (p.manufacturer_sku or "").strip():
                cat_slug = slugify(p.category.name)[:8] if p.category_id else "item"
                updates["manufacturer_sku"] = f"{cat_slug.upper()}-{p.sku}"

            if not (p.barcode or "").strip():
                base = str(p.sku).zfill(8)
                updates["barcode"] = f"4600000{base}"

            for field in ("material", "purpose", "flavor", "composition", "shelf_life", "description"):
                if not (getattr(p, field) or "").strip():
                    updates[field] = texts[field]

            if not p.country_of_origin_id:
                updates["country_of_origin"] = self._ensure_country(p)

            if not p.color_id:
                updates["color"] = self._ensure_color(p)

            if not p.series_id:
                series = self._ensure_series(p)
                if series:
                    updates["series"] = series

            self._fill_numeric(p, updates)

            if updates:
                for key, val in updates.items():
                    setattr(p, key, val)
                p.save(update_fields=list(updates.keys()))
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(f"Updated products: {updated_count}"))
