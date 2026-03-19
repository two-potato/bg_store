from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from random import Random
import re

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from PIL import Image, ImageDraw

from catalog.models import (
    Brand,
    Category,
    Collection,
    CollectionItem,
    Color,
    Country,
    Product,
    ProductImage,
    Series,
    Tag,
)


ROOT_CATEGORIES = [
    "Посуда для подачи",
    "Кухонная посуда",
    "Барное стекло и аксессуары",
    "Столовые приборы",
    "Текстиль для зала",
    "Хранение и GN-ёмкости",
    "Поварской инвентарь",
    "Буфет и подача",
    "Расходники для HoReCa",
    "Сервис и оснащение зала",
    "Оснащение для отелей",
    "Takeaway и упаковка",
    "Кофе, чай и бариста",
    "Кондитерский инвентарь",
]

ROOT_ALIASES = {
    "Сервировочная посуда": "Посуда для подачи",
    "Профессиональная кухня": "Кухонная посуда",
    "Стекло и бар": "Барное стекло и аксессуары",
    "Столовые приборы": "Столовые приборы",
    "Текстиль и униформа": "Текстиль для зала",
    "Гастроёмкости и хранение": "Хранение и GN-ёмкости",
    "Инвентарь кухни": "Поварской инвентарь",
    "Подача и буфет": "Буфет и подача",
    "Расходные материалы": "Расходники для HoReCa",
    "Товары для зала": "Сервис и оснащение зала",
    "Товары для отелей": "Оснащение для отелей",
    "Упаковка и takeaway": "Takeaway и упаковка",
    "Кофе и чай": "Кофе, чай и бариста",
    "Кондитерское направление": "Кондитерский инвентарь",
}

SUBCATEGORY_POOLS = {
    "Посуда для подачи": ["Тарелки и блюда", "Салатники и чаши", "Посуда для сервировки", "Блюда для подачи", "Фарфоровые коллекции", "Посуда для ресторанов"],
    "Кухонная посуда": ["Кастрюли", "Сковороды и сотейники", "Формы и противни", "Крышки", "Посуда для приготовления", "Кухонные решения"],
    "Барное стекло и аксессуары": ["Винные бокалы", "Коктейльные бокалы", "Стаканы и хайболы", "Шейкеры и джиггеры", "Барные аксессуары", "Стекло для бара"],
    "Столовые приборы": ["Ложки", "Вилки", "Ножи", "Сервировочные приборы", "Десертные приборы", "Наборы приборов"],
    "Текстиль для зала": ["Салфетки", "Скатерти", "Дорожки на стол", "Фартуки и униформа", "Кухонный текстиль", "Текстиль для сервиса"],
    "Хранение и GN-ёмкости": ["GN-ёмкости", "Крышки", "Контейнеры для хранения", "Лотки и боксы", "Организация хранения", "Инвентарь для склада"],
    "Поварской инвентарь": ["Лопатки и щипцы", "Половники и венчики", "Сита и дуршлаги", "Разделочные доски", "Ножи и аксессуары", "Кухонный инструмент"],
    "Буфет и подача": ["Подносы", "Этажерки", "Подставки", "Буфетные решения", "Доски для подачи", "Банкетная подача"],
    "Расходники для HoReCa": ["Перчатки", "Пленка и фольга", "Салфетки и полотенца", "Пакеты и мешки", "Гигиена персонала", "Уход и клининг"],
    "Сервис и оснащение зала": ["Меню и тейбл-тенты", "Номера столов", "Органайзеры", "Подставки", "Подносы официанта", "Аксессуары для сервиса"],
    "Оснащение для отелей": ["Room service", "Аксессуары для номера", "Лобби и буфет", "Гостевые наборы", "Оснащение ванной", "Гостевой сервис"],
    "Takeaway и упаковка": ["Стаканы и крышки", "Контейнеры", "Ланч-боксы", "Крафтовые пакеты", "Приборы takeaway", "Упаковка для доставки"],
    "Кофе, чай и бариста": ["Чашки и блюдца", "Чайники", "Френч-прессы", "Аксессуары бариста", "Кофейная подача", "Чайная подача"],
    "Кондитерский инвентарь": ["Формы и кольца", "Шпатели и скребки", "Подставки для десертов", "Силиконовые коврики", "Инвентарь для декора", "Инструменты кондитера"],
}

BRAND_NAMES = [
    "Complaex Signature",
    "North Pour",
    "Forma Barworks",
    "Copper Line Kitchen",
    "Mira Glass Lab",
    "Port & Pour",
    "Rivora Table",
    "Lume Service",
    "Crafted Horeca",
    "Madera Host",
    "Linea Pro Supply",
    "Brava Table",
    "Aster Mixology",
    "Cento Kitchen Goods",
    "Arco Guest",
    "Fluent Chef",
    "Vela Dining",
    "Nomad Utility",
    "Soma Buffet Lab",
    "Velour Service Textile",
]

SERIES_TOKENS = [
    "Night Shift",
    "Copper Mood",
    "Graphite Pour",
    "Cloud White",
    "Amber Rim",
    "Steel Pulse",
    "Velvet Service",
    "Flow Glass",
    "Bar Stage",
    "Stone Touch",
    "Urban Buffet",
    "Morning Roast",
]

COLLECTION_SPECS = [
    ("Барная карта", "Лучшее для коктейльной подачи, винной карты и интенсивной барной работы."),
    ("Кухня в потоке", "Позиции для горячего цеха, заготовки и стабильной ежедневной нагрузки."),
    ("Сервис без пауз", "Оснащение зала и сервиса, которое помогает держать стандарт на каждой смене."),
    ("Takeaway ready", "Упаковка и расходники для доставки, кофе навынос и быстрого сервиса."),
    ("Coffee point", "Товары для кофеен, бариста и чайной подачи."),
    ("Dessert pass", "Кондитерский инвентарь и решения для красивой десертной витрины."),
]

COLOR_DEFAULTS = [
    ("Графит", "#4A4A4A"),
    ("Янтарный", "#C6862A"),
    ("Молочный", "#F3EFE6"),
    ("Полночный синий", "#243447"),
]

COUNTRY_DEFAULTS = [
    ("Италия", "ITA"),
    ("Турция", "TUR"),
    ("Россия", "RUS"),
    ("Китай", "CHN"),
]

USAGE_TAGS = {
    "Посуда для подачи": "Для сервировки",
    "Кухонная посуда": "Для кухни",
    "Барное стекло и аксессуары": "Для бара",
    "Столовые приборы": "Для сервировки",
    "Текстиль для зала": "Для зала",
    "Хранение и GN-ёмкости": "Для хранения",
    "Поварской инвентарь": "Для кухни",
    "Буфет и подача": "Для буфета",
    "Расходники для HoReCa": "Для HoReCa",
    "Сервис и оснащение зала": "Для сервиса",
    "Оснащение для отелей": "Для отелей",
    "Takeaway и упаковка": "Для takeaway",
    "Кофе, чай и бариста": "Для кофе и чая",
    "Кондитерский инвентарь": "Для кондитерского цеха",
}

PROFILE_MAP = {
    "Посуда для подачи": {
        "types": ["Тарелка для подачи", "Тарелка глубокая", "Блюдо овальное", "Салатник", "Чаша для сервировки", "Тарелка coupe"],
        "materials": ["фарфор", "каменная керамика", "усиленный фарфор"],
        "series": ["Cloud White", "Amber Rim", "Stone Touch", "Velvet Service"],
        "sizes": ["21 см", "24 см", "26 см", "28 см", "30 см"],
    },
    "Кухонная посуда": {
        "types": ["Кастрюля", "Сотейник", "Сковорода", "Противень", "Гастроформа", "Крышка"],
        "materials": ["нержавеющая сталь", "алюминий", "антипригарное покрытие"],
        "series": ["Steel Pulse", "Copper Mood", "Night Shift", "Chef Line"],
        "sizes": ["24 см", "28 см", "32 см", "36 см"],
    },
    "Барное стекло и аксессуары": {
        "types": ["Бокал для вина", "Стакан хайбол", "Стакан old fashioned", "Бокал для игристого", "Шейкер барный", "Джиггер"],
        "materials": ["закаленное стекло", "хрустальное стекло", "нержавеющая сталь"],
        "series": ["Flow Glass", "Bar Stage", "Amber Rim", "Night Shift"],
        "sizes": ["250 мл", "320 мл", "420 мл", "500 мл", "650 мл"],
    },
    "Столовые приборы": {
        "types": ["Ложка столовая", "Вилка столовая", "Нож столовый", "Ложка десертная", "Вилка сервировочная", "Ложка для подачи"],
        "materials": ["полированная сталь", "матовая сталь", "нержавеющая сталь"],
        "series": ["Steel Pulse", "Urban Buffet", "Velvet Service", "Classic Host"],
        "sizes": ["стандарт", "десерт", "сервировочная"],
    },
    "Текстиль для зала": {
        "types": ["Салфетка текстильная", "Скатерть", "Фартук", "Полотенце", "Дорожка на стол", "Китель повара"],
        "materials": ["хлопок", "смесовая ткань", "плотный текстиль"],
        "series": ["Velvet Service", "Soft Hall", "Daily Host", "Night Shift"],
        "sizes": ["45×45 см", "50×70 см", "140×220 см", "one size"],
    },
    "Хранение и GN-ёмкости": {
        "types": ["GN-ёмкость", "Контейнер для хранения", "Крышка для GN", "Лоток", "Бокс для склада", "Контейнер с крышкой"],
        "materials": ["поликарбонат", "нержавеющая сталь", "полипропилен"],
        "series": ["Steel Pulse", "Storage Grid", "Core Box", "Night Shift"],
        "sizes": ["1/1", "1/2", "100 мм", "150 мм", "6 л"],
    },
    "Поварской инвентарь": {
        "types": ["Щипцы", "Лопатка", "Половник", "Венчик", "Сито", "Доска разделочная"],
        "materials": ["нержавеющая сталь", "силикон", "пищевой пластик", "дерево"],
        "series": ["Chef Line", "Prep Motion", "Daily Host", "Steel Pulse"],
        "sizes": ["28 см", "32 см", "36 см", "GN формат"],
    },
    "Буфет и подача": {
        "types": ["Поднос", "Этажерка", "Доска для подачи", "Буфетная подставка", "Колпак для подачи", "Блюдо банкетное"],
        "materials": ["дерево", "металл", "стекло", "фарфор"],
        "series": ["Urban Buffet", "Flow Glass", "Amber Rim", "Velvet Service"],
        "sizes": ["30 см", "36 см", "40 см", "GN формат"],
    },
    "Расходники для HoReCa": {
        "types": ["Перчатки", "Пленка пищевая", "Бумажные полотенца", "Пакет", "Мешок для мусора", "Салфетки одноразовые"],
        "materials": ["нитрил", "полиэтилен", "целлюлоза", "комбинированный материал"],
        "series": ["Daily Host", "Clean Shift", "Service Pack", "Kitchen Flow"],
        "sizes": ["100 шт", "45 см", "200 листов", "60 л"],
    },
    "Сервис и оснащение зала": {
        "types": ["Тейбл-тент", "Номер стола", "Подставка под меню", "Поднос официанта", "Органайзер сервиса", "Подставка под приборы"],
        "materials": ["акрил", "металл", "дерево", "поликарбонат"],
        "series": ["Front Shift", "Velvet Service", "Urban Buffet", "Guest Line"],
        "sizes": ["A6", "A5", "стандарт", "28 см"],
    },
    "Оснащение для отелей": {
        "types": ["Поднос room service", "Органайзер гостевого набора", "Корзина для номера", "Диспенсер", "Подставка для багажа", "Лоток amenity"],
        "materials": ["металл", "эко-кожа", "дерево", "поликарбонат"],
        "series": ["Guest Line", "Velvet Service", "Urban Buffet", "Soft Hall"],
        "sizes": ["32 см", "36 см", "40 см", "стандарт"],
    },
    "Takeaway и упаковка": {
        "types": ["Контейнер takeaway", "Бумажный стакан", "Крышка для стакана", "Ланч-бокс", "Крафтовый пакет", "Набор приборов takeaway"],
        "materials": ["крафт-картон", "полипропилен", "бумага", "bagasse"],
        "series": ["Go Service", "Urban To Go", "Daily Host", "Coffee Point"],
        "sizes": ["250 мл", "350 мл", "500 мл", "750 мл", "800 мл"],
    },
    "Кофе, чай и бариста": {
        "types": ["Чашка для капучино", "Блюдце", "Чайник", "Френч-пресс", "Сахарница", "Стакан для латте"],
        "materials": ["фарфор", "стекло", "нержавеющая сталь"],
        "series": ["Morning Roast", "Coffee Point", "Cloud White", "Tea Session"],
        "sizes": ["180 мл", "220 мл", "350 мл", "600 мл"],
    },
    "Кондитерский инвентарь": {
        "types": ["Кондитерское кольцо", "Шпатель", "Силиконовый коврик", "Форма для выпечки", "Подставка для десертов", "Скребок"],
        "materials": ["нержавеющая сталь", "силикон", "алюминий"],
        "series": ["Dessert Pass", "Sweet Line", "Copper Mood", "Pastry Lab"],
        "sizes": ["18 см", "24 см", "30 см", "60×40 см"],
    },
}


@dataclass
class ProductProfile:
    type_name: str
    material: str
    series_name: str
    size_label: str


class Command(BaseCommand):
    help = "Refresh catalog copy and structure for complaexbar.ru"

    def handle(self, *args, **options):
        self.random = Random(20260311)
        self.media_root = Path(settings.MEDIA_ROOT)
        self.tag_cache: dict[str, Tag] = {}
        self._ensure_dirs()
        with transaction.atomic():
            self._ensure_fallback_entities()
            self._refresh_categories()
            self._refresh_brands_and_series()
            self._reset_tags()
            self._refresh_products()
            self._refresh_collections()
        self.stdout.write(self.style.SUCCESS("complaexbar catalog refresh completed"))

    def _ensure_dirs(self) -> None:
        for rel in ["complaexbar/products", "complaexbar/collections"]:
            (self.media_root / rel).mkdir(parents=True, exist_ok=True)

    def _ensure_fallback_entities(self) -> None:
        self.fallback_brand, _ = Brand.objects.get_or_create(name="Complaex Essentials")
        self.fallback_category, _ = Category.objects.get_or_create(name="Базовое оснащение", parent=None)

    def _refresh_categories(self) -> None:
        top_categories = list(Category.objects.filter(parent__isnull=True).order_by("id"))
        for idx, category in enumerate(top_categories):
            original = category.name.strip()
            canonical = ROOT_ALIASES.get(original)
            if not canonical:
                canonical = ROOT_CATEGORIES[idx % len(ROOT_CATEGORIES)]
                if idx >= len(ROOT_CATEGORIES):
                    canonical = f"{canonical} {idx // len(ROOT_CATEGORIES) + 1}"
            category.name = canonical
            category.description = (
                f"{canonical} для баров, кофеен, ресторанов и гостиничных проектов на витрине complaexbar.ru. "
                "Категория собрана под реальные сценарии закупки и регулярной эксплуатации."
            )
            category.hero_title = canonical
            category.hero_text = f"Практичный ассортимент направления «{canonical.lower()}» для профессионального сервиса."
            category.landing_body = (
                f"В разделе «{canonical}» мы собрали позиции, которые нужны заведению в ежедневной работе: "
                "понятные спецификации, стабильная поставка и аккуратная подача на витрине complaexbar.ru."
            )
            category.faq_title = f"Как выбрать {canonical.lower()}?"
            category.faq_body = (
                "Смотрите на интенсивность нагрузки, материал, формат хранения и сценарий использования: "
                "бар, кухня, зал, takeaway или гостиничный сервис."
            )
            category.meta_title = f"{canonical} | complaexbar.ru"
            category.meta_description = f"{canonical} для HoReCa на complaexbar.ru: каталог для бара, кухни и сервиса."
            category.meta_keywords = f"complaexbar,{slugify(canonical).replace('-', ',')},horeca"
            category.slug = ""
            category.save()

            subcategories = list(Category.objects.filter(parent=category).order_by("id"))
            pool = SUBCATEGORY_POOLS.get(canonical, [f"{canonical} для HoReCa"])
            for child_idx, child in enumerate(subcategories):
                base = pool[child_idx % len(pool)]
                suffix = child_idx // len(pool) + 1
                child.name = base if suffix == 1 else f"{base} {suffix}"
                child.description = f"{child.name} для заведений HoReCa и b2b-закупок на complaexbar.ru."
                child.hero_title = child.name
                child.hero_text = f"Подкатегория «{child.name.lower()}» для точной закупки без лишнего выбора."
                child.landing_body = (
                    f"{child.name} помогает быстро собрать рабочую матрицу товаров внутри направления «{canonical}»."
                )
                child.faq_title = f"Что важно в разделе «{child.name}»?"
                child.faq_body = "Ориентируйтесь на размер, материал, формат подачи и устойчивость к ежедневной нагрузке."
                child.meta_title = f"{child.name} | complaexbar.ru"
                child.meta_description = f"{child.name} для HoReCa в каталоге complaexbar.ru."
                child.meta_keywords = f"complaexbar,{slugify(child.name).replace('-', ',')},category"
                child.slug = ""
                child.save()

    def _refresh_brands_and_series(self) -> None:
        brands = list(Brand.objects.order_by("id"))
        for idx, brand in enumerate(brands):
            brand.name = BRAND_NAMES[idx] if idx < len(BRAND_NAMES) else f"Complaex Partner {idx + 1}"
            brand.description = (
                f"{brand.name} поставляет продуманные позиции для бара, кухни, сервиса и гостевых пространств. "
                "На complaexbar.ru бренд собран как рабочий ассортимент для HoReCa, а не как декоративная витрина."
            )
            brand.landing_body = (
                f"{brand.name} выбирают за спокойный дизайн, понятную спецификацию и стабильность в ежедневной эксплуатации."
            )
            brand.faq_title = f"Почему выбирают {brand.name}?"
            brand.faq_body = "За универсальность, профессиональный внешний вид и предсказуемый результат в работе смены."
            brand.meta_title = f"{brand.name} | complaexbar.ru"
            brand.meta_description = f"{brand.name} в каталоге complaexbar.ru: товары для HoReCa и профессионального сервиса."
            brand.meta_keywords = f"complaexbar,{slugify(brand.name).replace('-', ',')},brand"
            brand.slug = ""
            brand.save()

        series_items = list(Series.objects.select_related("brand").order_by("id"))
        per_brand_counter: dict[int, int] = {}
        for series in series_items:
            counter = per_brand_counter.get(series.brand_id, 0)
            per_brand_counter[series.brand_id] = counter + 1
            token = SERIES_TOKENS[counter % len(SERIES_TOKENS)]
            if counter >= len(SERIES_TOKENS):
                token = f"{token} {counter // len(SERIES_TOKENS) + 1}"
            series.name = token
            series.description = f"{token} — рабочая серия бренда {series.brand.name} для каталога complaexbar.ru."
            series.meta_title = f"{series.brand.name} {token}"
            series.meta_description = f"Серия {token} бренда {series.brand.name} для бара, кухни и сервиса."
            series.meta_keywords = f"complaexbar,{slugify(token).replace('-', ',')},series"
            series.save()

    def _reset_tags(self) -> None:
        Tag.objects.all().delete()
        self.tag_cache.clear()

    def _refresh_products(self) -> None:
        products = list(
            Product.objects.select_related("category", "category__parent", "brand", "series", "country_of_origin", "color")
            .prefetch_related("images")
            .order_by("id")
        )
        seen_names: set[str] = set()
        for idx, product in enumerate(products):
            if not product.brand_id:
                product.brand = self.fallback_brand
            if not product.category_id:
                product.category = self.fallback_category

            root_name = self._canonical_root(
                product.category.parent.name if product.category and product.category.parent_id else product.category.name
            )
            profile = self._profile_for(root_name, idx)
            product.series = self._ensure_series(product, profile.series_name)
            product.country_of_origin = self._ensure_country(product, idx)
            product.color = self._ensure_color(product, idx)

            base_name = f"{profile.type_name} {product.series.name} {profile.size_label}".strip()
            if base_name in seen_names:
                base_name = f"{profile.type_name} {product.series.name} {product.sku[-2:]}"
            seen_names.add(base_name)

            product.name = base_name
            product.material = product.material or profile.material
            product.purpose = self._purpose_for(root_name)
            product.flavor = self._flavor_for(root_name, idx)
            product.composition = self._composition_for(root_name, product.material)
            product.shelf_life = product.shelf_life or self._shelf_life_for(root_name)
            product.manufacturer_sku = product.manufacturer_sku or f"CBR-{product.sku}"
            product.barcode = product.barcode or f"460{str(product.sku).zfill(10)}"
            product.meta_title = f"{base_name} | complaexbar.ru"
            product.meta_description = f"{base_name} для HoReCa: рабочая позиция для бара, кухни и сервиса на complaexbar.ru."
            product.meta_keywords = f"complaexbar,{slugify(profile.type_name).replace('-', ',')},{slugify(product.series.name).replace('-', ',')}"
            product.description = self._description_for(product, root_name, profile)
            product.attributes = {
                "Проект": "complaexbar.ru",
                "Категория": root_name,
                "Серия": product.series.name,
                "Материал": product.material.title(),
                "Формат поставки": f"{max(product.pack_qty, 1)} {product.unit or 'шт'}",
            }
            product.pack_qty = max(product.pack_qty, 1)
            product.unit = product.unit or "шт"
            product.price = product.price if product.price and product.price > 0 else Decimal("790.00")
            product.stock_qty = max(product.stock_qty, 12)
            product.min_order_qty = max(product.min_order_qty, 1)
            product.lead_time_days = max(product.lead_time_days, 1)
            product.publication_status = Product.PublicationStatus.PUBLISHED
            product.slug = ""
            product.save()

            self._sync_product_tags(product, root_name, profile)
            self._ensure_product_image(product, idx)
            if idx and idx % 500 == 0:
                self.stdout.write(f"complaexbar_refresh_catalog: processed {idx}/{len(products)} products")

    def _refresh_collections(self) -> None:
        CollectionItem.objects.all().delete()
        Collection.objects.all().delete()

        roots = {
            "Барная карта": "Барное стекло и аксессуары",
            "Кухня в потоке": "Кухонная посуда",
            "Сервис без пауз": "Сервис и оснащение зала",
            "Takeaway ready": "Takeaway и упаковка",
            "Coffee point": "Кофе, чай и бариста",
            "Dessert pass": "Кондитерский инвентарь",
        }
        for idx, (name, description) in enumerate(COLLECTION_SPECS):
            collection = Collection.objects.create(
                name=name,
                description=description,
                hero_title=name,
                hero_text=f"{name} на complaexbar.ru: подборка без случайных позиций и пустых карточек.",
                landing_body=(
                    f"Коллекция «{name}» собрана под конкретный сценарий закупки: "
                    "ускорить выбор, держать единый стиль и не тратить время на доработку карточек."
                ),
                faq_title=f"Для чего коллекция «{name}»?",
                faq_body="Чтобы быстро собрать рабочий набор товаров под задачу смены, открытия точки или обновления сервиса.",
                meta_title=f"{name} | complaexbar.ru",
                meta_description=f"{name} на complaexbar.ru: тематическая подборка для HoReCa.",
                meta_keywords=f"complaexbar,{slugify(name).replace('-', ',')},collection",
                is_active=True,
                is_featured=idx < 3,
            )
            root_name = roots.get(name, "Посуда для подачи")
            products = list(
                Product.objects.filter(category__name=root_name).order_by("-is_new", "-is_promo", "id")[:24]
            )
            if not products:
                products = list(Product.objects.order_by("-is_new", "-is_promo", "id")[:24])
            for position, product in enumerate(products):
                CollectionItem.objects.create(
                    collection=collection,
                    product=product,
                    ordering=position,
                    highlight=self._collection_highlight(name, product),
                )

    def _canonical_root(self, name: str) -> str:
        return ROOT_ALIASES.get((name or "").strip(), (name or "").strip())

    def _profile_for(self, root_name: str, idx: int) -> ProductProfile:
        pool = PROFILE_MAP.get(root_name) or PROFILE_MAP["Посуда для подачи"]
        return ProductProfile(
            type_name=pool["types"][idx % len(pool["types"])],
            material=pool["materials"][idx % len(pool["materials"])],
            series_name=pool["series"][idx % len(pool["series"])],
            size_label=pool["sizes"][idx % len(pool["sizes"])],
        )

    def _ensure_series(self, product: Product, series_name: str) -> Series | None:
        if not product.brand_id:
            return None
        if product.series_id:
            return product.series
        series, _ = Series.objects.get_or_create(
            brand=product.brand,
            name=series_name,
            defaults={
                "description": f"{series_name} — серия для проекта complaexbar.ru.",
                "meta_title": f"{product.brand.name} {series_name}",
                "meta_description": f"Серия {series_name} бренда {product.brand.name}.",
                "meta_keywords": f"complaexbar,{slugify(series_name).replace('-', ',')},series",
            },
        )
        return series

    def _ensure_country(self, product: Product, idx: int) -> Country:
        if product.country_of_origin_id:
            return product.country_of_origin
        name, iso = COUNTRY_DEFAULTS[idx % len(COUNTRY_DEFAULTS)]
        country, _ = Country.objects.get_or_create(name=name, defaults={"iso_code": iso})
        return country

    def _ensure_color(self, product: Product, idx: int) -> Color:
        if product.color_id:
            return product.color
        name, hex_code = COLOR_DEFAULTS[idx % len(COLOR_DEFAULTS)]
        color, _ = Color.objects.get_or_create(name=name, defaults={"hex_code": hex_code})
        if not color.hex_code:
            color.hex_code = hex_code
            color.save(update_fields=["hex_code"])
        return color

    def _purpose_for(self, root_name: str) -> str:
        mapping = {
            "Барное стекло и аксессуары": "Для коктейльной подачи, винной карты и барной станции",
            "Кухонная посуда": "Для горячего цеха, заготовки и ежедневной кухонной нагрузки",
            "Кофе, чай и бариста": "Для кофейной станции, чайной карты и сервиса напитков",
            "Takeaway и упаковка": "Для доставки, кофе навынос и быстрого сервиса",
        }
        return mapping.get(root_name, f"Для ежедневной работы направления «{root_name.lower()}»")

    def _flavor_for(self, root_name: str, idx: int) -> str:
        if root_name == "Кофе, чай и бариста":
            palette = ["карамельный", "ореховый", "цветочный", "классический"]
            return palette[idx % len(palette)]
        if root_name == "Барное стекло и аксессуары":
            return "нейтральный"
        return "без вкусового акцента"

    def _composition_for(self, root_name: str, material: str) -> str:
        if root_name in {"Кофе, чай и бариста", "Takeaway и упаковка", "Расходники для HoReCa"}:
            return f"Основной материал: {material}. Позиция адаптирована под интенсивную эксплуатацию в HoReCa."
        return f"Рабочий материал: {material}. Изделие рассчитано на ежедневное использование в проекте complaexbar.ru."

    def _shelf_life_for(self, root_name: str) -> str:
        if root_name in {"Кофе, чай и бариста", "Takeaway и упаковка", "Расходники для HoReCa"}:
            return "24 месяца"
        return "36 месяцев"

    def _description_for(self, product: Product, root_name: str, profile: ProductProfile) -> str:
        brand_name = product.brand.name if product.brand_id else "Complaex Essentials"
        country_name = product.country_of_origin.name if product.country_of_origin_id else "Россия"
        return (
            f"{product.name} от {brand_name} собран для витрины complaexbar.ru как понятная рабочая позиция для HoReCa. "
            f"Товар подходит для направления «{root_name.lower()}», выдерживает ежедневную сменную нагрузку и помогает держать единый визуальный стандарт.\n\n"
            f"Материал: {product.material}. Серия: {product.series.name if product.series_id else profile.series_name}. "
            f"Страна происхождения: {country_name}. Формат поставки: {max(product.pack_qty, 1)} {product.unit or 'шт'}. "
            "Карточка заполнена без технических заглушек: с назначением, описанием, базовыми характеристиками и корректными тегами."
        )

    def _sync_product_tags(self, product: Product, root_name: str, profile: ProductProfile) -> None:
        names = [
            root_name,
            profile.type_name,
            profile.material.title(),
            product.series.name if product.series_id else profile.series_name,
            USAGE_TAGS.get(root_name, "Для HoReCa"),
            "complaexbar.ru",
        ]
        if product.volume_ml:
            names.append(f"{int(product.volume_ml)} мл")
        elif product.diameter_mm:
            diameter_cm = float(product.diameter_mm) / 10
            names.append(f"{diameter_cm:.0f} см" if diameter_cm.is_integer() else f"{diameter_cm:.1f} см")
        if product.is_new:
            names.append("Новинка")
        if product.is_promo:
            names.append("Акция")

        unique_names: list[str] = []
        seen: set[str] = set()
        for name in names:
            normalized = (name or "").strip()
            if not normalized:
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            unique_names.append(normalized)

        product.tags.set([self._get_or_create_tag(name) for name in unique_names])

    def _get_or_create_tag(self, name: str) -> Tag:
        cached = self.tag_cache.get(name)
        if cached:
            return cached
        base_slug = slugify(name) or "complaexbar-tag"
        candidate = base_slug
        suffix = 2
        while Tag.objects.filter(slug=candidate).exclude(name=name).exists():
            candidate = f"{base_slug}-{suffix}"
            suffix += 1
        tag, _ = Tag.objects.get_or_create(name=name, defaults={"slug": candidate})
        if tag.slug != candidate:
            tag.slug = candidate
            tag.save(update_fields=["slug"])
        self.tag_cache[name] = tag
        return tag

    def _ensure_product_image(self, product: Product, idx: int) -> None:
        image = product.images.order_by("ordering", "id").first()
        if image:
            image.alt = product.name[:255]
            image.is_primary = True
            image.ordering = 0
            image.save(update_fields=["alt", "is_primary", "ordering"])
            return

        rel = f"complaexbar/products/{product.sku}.png"
        path = self.media_root / rel
        if not path.exists():
            self._generate_image(path, idx)
        ProductImage.objects.create(
            product=product,
            url=self._public_media_url(rel),
            alt=product.name[:255],
            is_primary=True,
            ordering=0,
        )

    def _collection_highlight(self, collection_name: str, product: Product) -> str:
        if collection_name == "Барная карта":
            return "Для интенсивной барной смены"
        if collection_name == "Кухня в потоке":
            return "Под горячий цех"
        if collection_name == "Coffee point":
            return "Для кофейной станции"
        return f"SKU {product.sku}"

    def _generate_image(self, path: Path, idx: int) -> None:
        width, height = 1200, 900
        bg_palette = [(22, 29, 37), (34, 44, 58), (72, 53, 42), (228, 222, 212)]
        accent_palette = [(198, 134, 42), (236, 236, 236), (121, 173, 220), (160, 97, 67)]
        bg = bg_palette[idx % len(bg_palette)]
        accent = accent_palette[idx % len(accent_palette)]
        image = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((120, 120, 1080, 780), radius=72, fill=(245, 241, 234), outline=accent, width=10)
        draw.ellipse((260, 220, 680, 640), fill=accent)
        draw.rounded_rectangle((700, 250, 980, 340), radius=28, fill=bg_palette[(idx + 1) % len(bg_palette)])
        draw.rounded_rectangle((700, 380, 1020, 450), radius=24, fill=accent_palette[(idx + 1) % len(accent_palette)])
        draw.rounded_rectangle((700, 490, 930, 550), radius=24, fill=accent_palette[(idx + 2) % len(accent_palette)])
        image.save(path)

    def _public_media_url(self, relative_path: str) -> str:
        configured = getattr(settings, "SERVIO_PUBLIC_BASE_URL", "").strip()
        if configured:
            base = configured.rstrip("/")
        elif settings.DEBUG:
            base = "http://localhost:8080"
        else:
            base = "https://complaexbar.ru"
        return f"{base}/media/{relative_path.lstrip('/')}"
