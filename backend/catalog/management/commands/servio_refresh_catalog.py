from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from random import Random
import re

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from PIL import Image, ImageDraw, ImageFilter

from catalog.models import Brand, Category, Product, ProductImage, Series, Tag
from commerce.models import SellerStore


ROOT_CATEGORIES = [
    "Сервировочная посуда",
    "Профессиональная кухня",
    "Стекло и бар",
    "Столовые приборы",
    "Текстиль и униформа",
    "Гастроёмкости и хранение",
    "Инвентарь кухни",
    "Подача и буфет",
    "Расходные материалы",
    "Товары для зала",
    "Товары для отелей",
    "Упаковка и takeaway",
    "Кофе и чай",
    "Кондитерское направление",
]

EXTRA_ROOT_CATEGORIES = [
    "Барные сиропы и топпинги",
    "Пюре и фруктовые основы",
    "Альтернативное молоко и сливки",
    "Одноразовая посуда",
    "Стаканы, крышки и трубочки",
    "Контейнеры для доставки",
    "Профессиональные ножи",
    "Разделочные доски",
    "Поварской инвентарь",
    "Кофейное зерно",
    "Чай и травяные сборы",
    "Барный лёд и аксессуары",
    "Десертная подача",
    "Банкетная подача",
    "Шведская линия и buffet",
    "Текстиль для зала",
    "Униформа персонала",
    "Гигиена и расходники",
    "Уборка и клининг",
    "Организация хранения",
    "Room service и amenity",
    "Лобби и гостевой сервис",
    "Кондитерский инвентарь",
    "Выпечка и формы",
    "Кофейная подача",
    "Чайная подача",
    "GN-ёмкости и крышки",
    "Барный инвентарь",
    "Сервировка стола",
    "Takeaway и упаковка",
]

ALL_ROOT_CATEGORIES = ROOT_CATEGORIES + EXTRA_ROOT_CATEGORIES

SUBCATEGORY_POOLS = {
    "Сервировочная посуда": ["Тарелки", "Блюда", "Салатники", "Чаши", "Соусники", "Подстановки"],
    "Профессиональная кухня": ["Кастрюли", "Сковороды", "Формы", "Противни", "Крышки", "Посуда для приготовления"],
    "Стекло и бар": ["Винные бокалы", "Барные стаканы", "Коктейльная подача", "Шейкеры и мерники", "Декантеры", "Барный инвентарь"],
    "Столовые приборы": ["Ложки", "Вилки", "Ножи", "Приборы для подачи", "Десертные приборы", "Наборы приборов"],
    "Текстиль и униформа": ["Салфетки", "Скатерти", "Фартуки", "Кухонный текстиль", "Дорожки на стол", "Рабочая форма"],
    "Гастроёмкости и хранение": ["GN-ёмкости", "Крышки", "Контейнеры", "Организация хранения", "Лотки", "Тележки и боксы"],
    "Инвентарь кухни": ["Лопатки", "Щипцы", "Половники", "Венчики", "Сита и дуршлаги", "Ножи и доски"],
    "Подача и буфет": ["Этажерки", "Подносы", "Колпаки", "Подставки", "Буфетные решения", "Сервировочные доски"],
    "Расходные материалы": ["Перчатки", "Пленка и фольга", "Салфетки и полотенца", "Мешки и пакеты", "Химия и уход", "Гигиена персонала"],
    "Товары для зала": ["Меню и тейбл-топы", "Нумерация столов", "Подставки", "Декор сервиса", "Стойки и аксессуары", "Решения для гостя"],
    "Товары для отелей": ["Room service", "Номерной сервис", "Гостевые аксессуары", "Текстиль номера", "Ванные принадлежности", "Лобби и буфет"],
    "Упаковка и takeaway": ["Контейнеры", "Стаканы и крышки", "Пакеты", "Ланч-боксы", "Приборы takeaway", "Решения для доставки"],
    "Кофе и чай": ["Чашки и блюдца", "Чайники", "Френч-прессы", "Кофейная подача", "Сахарницы", "Аксессуары бариста"],
    "Кондитерское направление": ["Формы и кольца", "Шпатели и скребки", "Подставки", "Маты и коврики", "Инвентарь декора", "Витринная подача"],
}

BRAND_NAMES = [
    "Servio Atelier",
    "Northline Table",
    "Forma Service",
    "Aurum Kitchen",
    "Mira Glassworks",
    "Portline Supply",
    "Rivora",
    "Lume Dining",
    "Crafto Horeca",
    "Madera Pro",
    "Linea Host",
    "Brava Tableware",
    "Aster Barware",
    "Cento Supply",
    "Arco Hotelware",
    "Fluent Kitchen",
    "Vela Service",
    "Noma Utility",
    "Soma Buffet",
    "Velour Textile",
]

SERIES_TOKENS = [
    "Nordic White",
    "Graphite Line",
    "Sand Studio",
    "Stone Mist",
    "Glass Arc",
    "Urban Steel",
    "Pure Flow",
    "Cobalt Rim",
    "Ivory Service",
    "Slate Edition",
    "Clear Volume",
    "Soft Linen",
]

STORE_NAMES = [
    "Servio Central Supply",
    "Northline Pro Store",
    "Forma HoReCa Hub",
    "Aurum Kitchen Market",
    "Lume Service Depot",
    "Portline Horeca Store",
]

SELLER_NAMES = [
    "Команда сервиса Север",
    "Отдел закупок Forma",
    "Aurum Supply Team",
    "Lume Professional",
    "Portline Trade Group",
    "Central Horeca Partner",
]

PROFILE_MAP = {
    "Сервировочная посуда": {
        "types": ["Тарелка сервировочная", "Тарелка глубокая", "Блюдо овальное", "Салатник", "Чаша для подачи", "Тарелка coupe"],
        "materials": ["фарфор", "каменная керамика", "усиленный фарфор"],
        "series": ["Nordic", "Forma", "Porto", "Luca"],
        "sizes": ["24 см", "26 см", "28 см", "30 см"],
        "visual": "plate",
    },
    "Профессиональная кухня": {
        "types": ["Кастрюля профессиональная", "Сотейник", "Сковорода", "Противень", "Форма гастрономическая", "Крышка усиленная"],
        "materials": ["нержавеющая сталь", "алюминий", "антипригарное покрытие"],
        "series": ["Chef Core", "Prime Heat", "Steel Work", "Line Pro"],
        "sizes": ["24 см", "28 см", "32 см", "36 см"],
        "visual": "cookware",
    },
    "Стекло и бар": {
        "types": ["Бокал для вина", "Стакан highball", "Стакан old fashioned", "Бокал для шампанского", "Шейкер барный", "Мерник двойной"],
        "materials": ["закаленное стекло", "хрустальное стекло", "нержавеющая сталь"],
        "series": ["Crystal", "Bar Motion", "Clear Session", "Mixology"],
        "sizes": ["320 мл", "420 мл", "500 мл", "650 мл"],
        "visual": "glass",
    },
    "Столовые приборы": {
        "types": ["Ложка столовая", "Вилка столовая", "Нож столовый", "Ложка десертная", "Вилка для подачи", "Ложка сервировочная"],
        "materials": ["нержавеющая сталь", "матовая сталь", "полированная сталь"],
        "series": ["Classic", "Studio", "Pure Steel", "Linear"],
        "sizes": ["стандарт", "десерт", "сервировочная"],
        "visual": "cutlery",
    },
    "Текстиль и униформа": {
        "types": ["Салфетка текстильная", "Скатерть", "Фартук поварской", "Полотенце кухонное", "Дорожка на стол", "Китель повара"],
        "materials": ["хлопок", "смесовая ткань", "плотный текстиль"],
        "series": ["Soft Line", "Chef Wear", "Table Textile", "Daily Fabric"],
        "sizes": ["45×45 см", "140×220 см", "one size", "50×70 см"],
        "visual": "textile",
    },
    "Гастроёмкости и хранение": {
        "types": ["Гастроёмкость GN 1/1", "Гастроёмкость GN 1/2", "Крышка для гастроёмкости", "Контейнер для хранения", "Лоток сервисный", "Бокс для склада"],
        "materials": ["поликарбонат", "нержавеющая сталь", "полипропилен"],
        "series": ["Storage Pro", "GN System", "Kitchen Hold", "Core Box"],
        "sizes": ["100 мм", "150 мм", "200 мм", "6 л"],
        "visual": "container",
    },
    "Инвентарь кухни": {
        "types": ["Щипцы кухонные", "Лопатка силиконовая", "Половник", "Венчик", "Сито", "Доска разделочная"],
        "materials": ["нержавеющая сталь", "силикон", "пищевой пластик", "дерево"],
        "series": ["Chef Motion", "Prep Line", "Utility", "Kitchen Sense"],
        "sizes": ["28 см", "32 см", "36 см", "GN формат"],
        "visual": "tool",
    },
    "Подача и буфет": {
        "types": ["Поднос сервировочный", "Этажерка", "Доска для подачи", "Подставка buffet", "Колпак для подачи", "Блюдо банкетное"],
        "materials": ["дерево", "фарфор", "стекло", "металл"],
        "series": ["Buffet Form", "Serve Flow", "Display", "Table Show"],
        "sizes": ["30 см", "36 см", "40 см", "GN формат"],
        "visual": "tray",
    },
    "Расходные материалы": {
        "types": ["Перчатки нитриловые", "Пленка пищевая", "Салфетки одноразовые", "Пакет хозяйственный", "Мешок для мусора", "Полотенца бумажные"],
        "materials": ["нитрил", "полиэтилен", "целлюлоза", "комбинированный материал"],
        "series": ["Daily Supply", "Clean Work", "Service Pack", "Flow Care"],
        "sizes": ["100 шт", "45 см", "200 листов", "60 л"],
        "visual": "package",
    },
    "Товары для зала": {
        "types": ["Подставка под меню", "Номер стола", "Тейбл-тент", "Поднос официанта", "Подставка под приборы", "Органайзер сервиса"],
        "materials": ["акрил", "металл", "дерево", "поликарбонат"],
        "series": ["Guest Flow", "Hall System", "Service Line", "Front Desk"],
        "sizes": ["A6", "A5", "стандарт", "28 см"],
        "visual": "sign",
    },
    "Товары для отелей": {
        "types": ["Поднос room service", "Органайзер гостевого набора", "Корзина для номера", "Диспенсер", "Подставка для багажа", "Лоток amenity"],
        "materials": ["металл", "эко-кожа", "дерево", "поликарбонат"],
        "series": ["Hotel Room", "Guest Care", "Lobby Service", "Amenity"],
        "sizes": ["32 см", "36 см", "40 см", "стандарт"],
        "visual": "hotel",
    },
    "Упаковка и takeaway": {
        "types": ["Контейнер takeaway", "Стакан бумажный", "Крышка для стакана", "Ланч-бокс", "Пакет крафтовый", "Набор приборов takeaway"],
        "materials": ["крафт-картон", "полипропилен", "бумага", "bagasse"],
        "series": ["Take Care", "Go Line", "Delivery Pack", "Urban To Go"],
        "sizes": ["350 мл", "500 мл", "750 мл", "800 мл"],
        "visual": "packaging",
    },
    "Кофе и чай": {
        "types": ["Чашка для капучино", "Блюдце", "Чайник", "Френч-пресс", "Сахарница", "Стакан для латте"],
        "materials": ["фарфор", "стекло", "нержавеющая сталь"],
        "series": ["Roast Line", "Tea Service", "Barista Core", "Milk Studio"],
        "sizes": ["180 мл", "220 мл", "350 мл", "600 мл"],
        "visual": "cup",
    },
    "Кондитерское направление": {
        "types": ["Кондитерское кольцо", "Шпатель", "Силиконовый коврик", "Форма для выпечки", "Подставка для десертов", "Скребок"],
        "materials": ["нержавеющая сталь", "силикон", "алюминий"],
        "series": ["Pastry Craft", "Sweet Line", "Bake Studio", "Dessert Form"],
        "sizes": ["18 см", "24 см", "30 см", "60×40 см"],
        "visual": "pastry",
    },
}

CATEGORY_ALIASES = {
    "Барные сиропы и топпинги": "Кофе и чай",
    "Пюре и фруктовые основы": "Кофе и чай",
    "Альтернативное молоко и сливки": "Кофе и чай",
    "Одноразовая посуда": "Упаковка и takeaway",
    "Стаканы, крышки и трубочки": "Упаковка и takeaway",
    "Контейнеры для доставки": "Упаковка и takeaway",
    "Профессиональные ножи": "Инвентарь кухни",
    "Разделочные доски": "Инвентарь кухни",
    "Поварской инвентарь": "Инвентарь кухни",
    "Кофейное зерно": "Кофе и чай",
    "Чай и травяные сборы": "Кофе и чай",
    "Барный лёд и аксессуары": "Стекло и бар",
    "Десертная подача": "Подача и буфет",
    "Банкетная подача": "Подача и буфет",
    "Шведская линия и buffet": "Подача и буфет",
    "Текстиль для зала": "Текстиль и униформа",
    "Униформа персонала": "Текстиль и униформа",
    "Гигиена и расходники": "Расходные материалы",
    "Уборка и клининг": "Расходные материалы",
    "Организация хранения": "Гастроёмкости и хранение",
    "Room service и amenity": "Товары для отелей",
    "Лобби и гостевой сервис": "Товары для отелей",
    "Кондитерский инвентарь": "Кондитерское направление",
    "Выпечка и формы": "Кондитерское направление",
    "Кофейная подача": "Кофе и чай",
    "Чайная подача": "Кофе и чай",
    "GN-ёмкости и крышки": "Гастроёмкости и хранение",
    "Барный инвентарь": "Стекло и бар",
    "Сервировка стола": "Сервировочная посуда",
    "Takeaway и упаковка": "Упаковка и takeaway",
}

USAGE_TAGS = {
    "Сервировочная посуда": "Для сервировки",
    "Профессиональная кухня": "Для кухни",
    "Стекло и бар": "Для бара",
    "Столовые приборы": "Для сервировки",
    "Текстиль и униформа": "Для зала",
    "Гастроёмкости и хранение": "Для хранения",
    "Инвентарь кухни": "Для кухни",
    "Подача и буфет": "Для буфета",
    "Расходные материалы": "Для расходников",
    "Товары для зала": "Для гостевого сервиса",
    "Товары для отелей": "Для отелей",
    "Упаковка и takeaway": "Для takeaway",
    "Кофе и чай": "Для кофе и чая",
    "Кондитерское направление": "Для кондитерского цеха",
}


@dataclass
class ProductProfile:
    type_name: str
    material: str
    series_name: str
    size_label: str
    visual: str


class Command(BaseCommand):
    help = "Rebrand catalog, pages and media to Servio HoReCa marketplace"

    def add_arguments(self, parser):
        parser.add_argument("--skip-images", action="store_true")

    def handle(self, *args, **options):
        self.media_root = Path(settings.MEDIA_ROOT)
        self.skip_images = bool(options["skip_images"])
        self.random = Random(20260309)
        self._tag_cache: dict[str, Tag] = {}

        self._ensure_dirs()
        with transaction.atomic():
            self._refresh_categories()
            self._refresh_brands()
            self._refresh_stores_and_profiles()
            self._reset_tags()
        self._refresh_products()
        if not self.skip_images:
            self._generate_hero_images()

        self.stdout.write(self.style.SUCCESS("Servio catalog refresh completed"))

    def _ensure_dirs(self):
        for rel in [
            "servio/products",
            "hero",
            "brand_photos",
            "seller_store_photos",
        ]:
            (self.media_root / rel).mkdir(parents=True, exist_ok=True)

    def _refresh_categories(self):
        top_categories = list(Category.objects.filter(parent__isnull=True).order_by("id"))
        for idx, category in enumerate(top_categories):
            name = self._root_category_name(idx)
            category.name = name
            category.description = f"{name} для ресторанов, кафе, баров, гостиниц и профессиональных кухонь."
            category.meta_title = f"{name} — каталог Servio"
            category.meta_description = f"{name} в маркетплейсе Servio: профессиональные товары для HoReCa и регулярных b2b-закупок."
            category.meta_keywords = f"servio,{slugify(name).replace('-', ',')},horeca"
            category.slug = ""
            category.save()

            subcategories = list(Category.objects.filter(parent=category).order_by("id"))
            pool = SUBCATEGORY_POOLS.get(self._canonical_root(name), [f"{name} — решения"])
            for child_idx, child in enumerate(subcategories):
                base = pool[child_idx % len(pool)]
                suffix = child_idx // len(pool) + 1
                child.name = base if suffix == 1 else f"{base} {suffix}"
                child.description = f"{child.name} в направлении «{name}» для каталога Servio."
                child.meta_title = f"{child.name} — Servio"
                child.meta_description = f"{child.name} для HoReCa в каталоге Servio."
                child.meta_keywords = f"servio,{slugify(child.name).replace('-', ',')},horeca"
                child.slug = ""
                child.save()

    def _refresh_brands(self):
        brands = list(Brand.objects.order_by("id"))
        for idx, brand in enumerate(brands):
            name = BRAND_NAMES[idx] if idx < len(BRAND_NAMES) else f"Servio Partner {idx + 1}"
            brand.name = name
            brand.description = f"{name} — коллекции и профессиональные решения для HoReCa-проектов в каталоге Servio."
            brand.meta_title = f"{name} — бренд Servio"
            brand.meta_description = f"Ассортимент бренда {name} в Servio: товары для кухни, сервировки, бара и гостевого сервиса."
            brand.meta_keywords = f"servio,{slugify(name).replace('-', ',')},brand"
            brand.save()
            self._ensure_brand_image(brand, idx)

        series_items = list(Series.objects.select_related("brand").order_by("id"))
        per_brand_counters: dict[int, int] = {}
        for idx, series in enumerate(series_items):
            brand_index = per_brand_counters.get(series.brand_id, 0)
            per_brand_counters[series.brand_id] = brand_index + 1
            token = SERIES_TOKENS[brand_index % len(SERIES_TOKENS)]
            if brand_index >= len(SERIES_TOKENS):
                token = f"{token} {brand_index // len(SERIES_TOKENS) + 1}"
            series.name = token
            series.description = f"{token} — серия бренда {series.brand.name} для каталога Servio."
            series.meta_title = f"{series.brand.name} {token}"
            series.meta_description = f"Серия {token} бренда {series.brand.name} в каталоге Servio."
            series.meta_keywords = f"servio,{slugify(token).replace('-', ',')},series"
            series.save()

    def _refresh_stores_and_profiles(self):
        stores = list(SellerStore.objects.select_related("owner", "owner__profile", "legal_entity").order_by("id"))
        for idx, store in enumerate(stores):
            store_name = STORE_NAMES[idx] if idx < len(STORE_NAMES) else f"Servio Supplier Hub {idx + 1}"
            seller_name = SELLER_NAMES[idx] if idx < len(SELLER_NAMES) else f"Поставщик Servio {idx + 1}"
            store.name = store_name
            store.description = f"{store_name} — витрина поставщика товаров для HoReCa в маркетплейсе Servio."
            store.slug = ""
            store.save()
            self._ensure_store_image(store, idx)

            profile = getattr(store.owner, "profile", None)
            if profile:
                profile.full_name = seller_name
                profile.contact_email = profile.contact_email or "hello@servio.market"
                profile.slug = ""
                profile.save()

            legal_entity = store.legal_entity
            legal_entity.name = f"{store_name} LLC"
            legal_entity.save(update_fields=["name"])

    def _refresh_products(self):
        products = list(
            Product.objects.select_related("category", "category__parent", "brand", "series", "seller", "seller__seller_store")
            .prefetch_related("images")
            .order_by("id")
        )
        used_names = set()
        for idx, product in enumerate(products):
            root_name = product.category.parent.name if product.category and product.category.parent else (product.category.name if product.category else self._root_category_name(idx))
            canonical_root = self._canonical_root(root_name)
            profile = self._profile_for(canonical_root, idx)
            base_name = f"{profile.type_name} {profile.series_name} {profile.size_label}".strip()
            if base_name in used_names:
                base_name = f"{profile.type_name} {profile.series_name} {profile.material.title()}"
            used_names.add(base_name)

            product.name = base_name
            product.material = profile.material
            product.purpose = f"Для направления «{canonical_root.lower()}»"
            product.description = (
                f"{base_name} — позиция для профессионального каталога Servio. "
                f"Подходит для заведений HoReCa, которым важны понятная спецификация, аккуратная подача и стабильный формат поставки.\n\n"
                f"Серия {profile.series_name} разработана для ежедневной работы кухни, бара, сервиса или гостевого пространства. "
                f"Товар удобно включать в регулярные закупки и использовать в операционных сценариях без лишних согласований."
            )
            product.meta_title = f"{base_name} — купить в Servio"
            product.meta_description = f"{base_name} в каталоге Servio: товары для HoReCa с понятной подачей, характеристиками и b2b-логикой закупки."
            product.meta_keywords = f"servio,{slugify(profile.type_name).replace('-', ',')},{slugify(profile.series_name).replace('-', ',')}"
            product.attributes = {
                "Назначение": canonical_root,
                "Линия": profile.series_name,
                "Материал": profile.material.title(),
                "Формат поставки": f"{max(product.pack_qty, 1)} {product.unit}",
            }
            product.composition = ""
            if canonical_root not in {"Кофе и чай"}:
                product.flavor = ""
            product.slug = ""
            product.save()
            self._sync_product_tags(product, root_name, canonical_root, profile)
            self._sync_product_image(product, profile.visual, idx)
            if idx and idx % 250 == 0:
                self.stdout.write(f"servio_refresh_catalog: processed {idx}/{len(products)} products")

    def _reset_tags(self):
        Tag.objects.all().delete()
        self._tag_cache.clear()

    def _sync_product_tags(self, product: Product, root_name: str, canonical_root: str, profile: ProductProfile):
        tag_names: list[str] = []

        if self._tag_allowed(root_name):
            tag_names.append(root_name)
        if canonical_root != root_name and self._tag_allowed(canonical_root):
            tag_names.append(canonical_root)

        if product.category_id:
            if product.category.parent_id:
                if self._tag_allowed(product.category.name):
                    tag_names.append(product.category.name)
            elif product.category.name != root_name and self._tag_allowed(product.category.name):
                tag_names.append(product.category.name)

        tag_names.append(profile.type_name)
        tag_names.append(profile.material.title())
        tag_names.append(profile.series_name)
        tag_names.append(USAGE_TAGS.get(canonical_root, "Для HoReCa"))

        if product.volume_ml:
            tag_names.append(f"{int(product.volume_ml)} мл")
        elif product.diameter_mm:
            diameter_cm = float(product.diameter_mm) / 10
            if diameter_cm.is_integer():
                tag_names.append(f"{int(diameter_cm)} см")
            else:
                tag_names.append(f"{diameter_cm:.1f} см")

        if product.is_new:
            tag_names.append("Новинка")
        if product.is_promo:
            tag_names.append("Акция")

        seen: set[str] = set()
        tags: list[Tag] = []
        for name in tag_names:
            normalized = (name or "").strip()
            if not normalized:
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            tags.append(self._get_or_create_tag(normalized))

        product.tags.set(tags)

    def _get_or_create_tag(self, name: str) -> Tag:
        cached = self._tag_cache.get(name)
        if cached:
            return cached

        base_slug = slugify(name) or "servio-tag"
        candidate = base_slug
        suffix = 2
        while Tag.objects.filter(slug=candidate).exclude(name=name).exists():
            candidate = f"{base_slug}-{suffix}"
            suffix += 1
        tag, _ = Tag.objects.get_or_create(name=name, defaults={"slug": candidate})
        if tag.slug != candidate:
            tag.slug = candidate
            tag.save(update_fields=["slug"])
        self._tag_cache[name] = tag
        return tag

    def _root_category_name(self, idx: int) -> str:
        base = ALL_ROOT_CATEGORIES[idx % len(ALL_ROOT_CATEGORIES)]
        cycle = idx // len(ALL_ROOT_CATEGORIES)
        return base if cycle == 0 else f"{base} {cycle + 1}"

    def _canonical_root(self, name: str) -> str:
        return CATEGORY_ALIASES.get(name, name)

    def _tag_allowed(self, name: str) -> bool:
        normalized = (name or "").strip()
        if not normalized:
            return False
        if re.match(r"^HoReCa направление \d+$", normalized):
            return False
        if re.match(r"^category-\d+$", normalized, flags=re.IGNORECASE):
            return False
        return True

    def _profile_for(self, root_name: str, idx: int) -> ProductProfile:
        source = PROFILE_MAP.get(root_name) or PROFILE_MAP["Сервировочная посуда"]
        type_name = source["types"][idx % len(source["types"])]
        material = source["materials"][idx % len(source["materials"])]
        series_seed = source["series"][idx % len(source["series"])]
        size_label = source["sizes"][idx % len(source["sizes"])]
        return ProductProfile(
            type_name=type_name,
            material=material,
            series_name=series_seed,
            size_label=size_label,
            visual=source["visual"],
        )

    def _sync_product_image(self, product: Product, visual: str, idx: int):
        image_rel = f"servio/products/{product.slug or slugify(product.name) or product.sku}.png"
        image_abs = self.media_root / image_rel
        if not self.skip_images and not image_abs.exists():
            self._generate_product_image(image_abs, visual, idx)

        url = self._public_media_url(image_rel)
        image = product.images.order_by("ordering", "id").first()
        use_generated_url = image_abs.exists()
        if image:
            if use_generated_url:
                image.url = url
            image.alt = product.name[:255]
            image.is_primary = True
            image.ordering = 0
            image.save()
            product.images.exclude(id=image.id).delete()
        else:
            ProductImage.objects.create(
                product=product,
                url=url if use_generated_url else self._public_media_url("hero/servio-hero-main.png"),
                alt=product.name[:255],
                is_primary=True,
                ordering=0,
            )

    def _ensure_brand_image(self, brand: Brand, idx: int):
        rel = f"brand_photos/{slugify(brand.name) or f'brand-{brand.id}'}.png"
        abs_path = self.media_root / rel
        if not self.skip_images and not abs_path.exists():
            self._generate_banner_image(abs_path, idx, form="brand")
        brand.photo.name = rel
        brand.save(update_fields=["photo"])

    def _ensure_store_image(self, store: SellerStore, idx: int):
        rel = f"seller_store_photos/{slugify(store.name) or f'store-{store.id}'}.png"
        abs_path = self.media_root / rel
        if not self.skip_images and not abs_path.exists():
            self._generate_banner_image(abs_path, idx, form="store")
        store.photo.name = rel
        store.save(update_fields=["photo"])

    def _generate_hero_images(self):
        targets = [
            ("hero/servio-hero-main.png", "plate", 11),
            ("hero/servio-hero-bar.png", "glass", 27),
            ("hero/servio-hero-tableware.png", "tray", 41),
        ]
        for rel, visual, seed in targets:
            abs_path = self.media_root / rel
            if not abs_path.exists():
                self._generate_product_image(abs_path, visual, seed, canvas=(1400, 920))

    def _generate_banner_image(self, path: Path, idx: int, form: str):
        size = (1600, 900)
        bg = self._background(size, idx)
        draw = ImageDraw.Draw(bg)
        accent = self._accent(idx)
        if form == "brand":
            draw.rounded_rectangle((140, 120, 1460, 780), radius=120, fill=(255, 255, 255, 235), outline=accent + (90,), width=8)
            draw.rounded_rectangle((240, 240, 620, 620), radius=120, fill=accent + (255,))
            draw.rounded_rectangle((720, 250, 1280, 340), radius=34, fill=(16, 32, 60, 220))
            draw.rounded_rectangle((720, 390, 1160, 450), radius=28, fill=(73, 95, 139, 160))
            draw.rounded_rectangle((720, 500, 1350, 560), radius=28, fill=(73, 95, 139, 120))
        else:
            draw.rounded_rectangle((120, 100, 1480, 800), radius=110, fill=(255, 255, 255, 230), outline=accent + (70,), width=8)
            draw.ellipse((210, 220, 540, 550), fill=accent + (255,))
            draw.rounded_rectangle((650, 210, 1340, 330), radius=34, fill=(16, 32, 60, 220))
            draw.rounded_rectangle((650, 380, 1240, 450), radius=26, fill=(73, 95, 139, 160))
            draw.rounded_rectangle((650, 500, 1140, 560), radius=26, fill=(73, 95, 139, 120))
        bg.save(path, format="PNG", compress_level=1)

    def _generate_product_image(self, path: Path, visual: str, idx: int, canvas: tuple[int, int] = (1200, 1200)):
        image = self._background(canvas, idx)
        shadow = Image.new("RGBA", canvas, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.ellipse((420, canvas[1] - 340, canvas[0] - 420, canvas[1] - 210), fill=(8, 19, 44, 60))
        shadow = shadow.filter(ImageFilter.GaussianBlur(22))
        image = Image.alpha_composite(image, shadow)

        draw = ImageDraw.Draw(image)
        accent = self._accent(idx)
        secondary = self._accent(idx + 3)

        if visual == "plate":
            draw.ellipse((380, 340, 1420, 1380), fill=(250, 252, 255, 255), outline=accent + (95,), width=20)
            draw.ellipse((520, 480, 1280, 1240), fill=(255, 255, 255, 255), outline=secondary + (65,), width=10)
        elif visual == "cookware":
            draw.rounded_rectangle((420, 680, 1380, 1120), radius=120, fill=(56, 66, 86, 255))
            draw.rounded_rectangle((540, 760, 1260, 1040), radius=80, fill=(86, 98, 120, 255))
            draw.rounded_rectangle((280, 820, 470, 920), radius=46, fill=accent + (255,))
            draw.rounded_rectangle((1330, 820, 1520, 920), radius=46, fill=accent + (255,))
        elif visual == "glass":
            draw.polygon([(760, 340), (1040, 340), (1120, 760), (680, 760)], fill=(255, 255, 255, 180), outline=accent + (110,))
            draw.rounded_rectangle((865, 760, 935, 1220), radius=30, fill=(221, 232, 255, 220))
            draw.rounded_rectangle((670, 1200, 1130, 1290), radius=38, fill=(246, 250, 255, 255), outline=secondary + (80,), width=8)
        elif visual == "cutlery":
            draw.rounded_rectangle((480, 340, 610, 1260), radius=44, fill=(240, 246, 255, 255), outline=accent + (90,), width=8)
            draw.rounded_rectangle((850, 340, 980, 1260), radius=44, fill=(240, 246, 255, 255), outline=secondary + (90,), width=8)
            draw.rounded_rectangle((1220, 340, 1330, 1260), radius=44, fill=(240, 246, 255, 255), outline=accent + (90,), width=8)
        elif visual == "textile":
            draw.rounded_rectangle((420, 420, 1380, 1200), radius=120, fill=(248, 250, 255, 255), outline=accent + (90,), width=10)
            draw.polygon([(520, 520), (1280, 520), (1140, 1100), (640, 1100)], fill=secondary + (120,))
        elif visual == "container":
            draw.rounded_rectangle((380, 540, 1420, 1160), radius=90, fill=(227, 236, 255, 255), outline=accent + (90,), width=12)
            draw.rounded_rectangle((470, 620, 1330, 1070), radius=66, fill=(255, 255, 255, 255), outline=secondary + (80,), width=8)
        elif visual == "tool":
            draw.rounded_rectangle((460, 320, 660, 1280), radius=56, fill=(244, 248, 255, 255), outline=accent + (80,), width=8)
            draw.rounded_rectangle((920, 320, 1120, 1280), radius=56, fill=(244, 248, 255, 255), outline=secondary + (80,), width=8)
        elif visual == "tray":
            draw.rounded_rectangle((330, 560, 1470, 1160), radius=110, fill=(123, 99, 73, 255), outline=accent + (70,), width=10)
            draw.rounded_rectangle((420, 650, 1380, 1070), radius=86, fill=(255, 255, 255, 220))
        elif visual == "package":
            draw.rounded_rectangle((460, 420, 1340, 1220), radius=100, fill=(255, 255, 255, 255), outline=accent + (90,), width=10)
            draw.rounded_rectangle((560, 520, 1240, 1120), radius=80, fill=(240, 246, 255, 255))
            draw.rounded_rectangle((760, 300, 1040, 520), radius=80, fill=secondary + (200,))
        elif visual == "sign":
            draw.rounded_rectangle((460, 340, 1340, 980), radius=70, fill=(255, 255, 255, 250), outline=accent + (90,), width=12)
            draw.rounded_rectangle((860, 980, 940, 1340), radius=40, fill=accent + (255,))
        elif visual == "hotel":
            draw.rounded_rectangle((390, 620, 1410, 1120), radius=100, fill=(245, 248, 255, 255), outline=accent + (90,), width=10)
            draw.rounded_rectangle((520, 500, 1280, 760), radius=70, fill=secondary + (140,))
        elif visual == "packaging":
            draw.rounded_rectangle((470, 430, 1330, 1240), radius=120, fill=(255, 255, 255, 255), outline=accent + (90,), width=10)
            draw.rounded_rectangle((620, 260, 1180, 470), radius=100, fill=accent + (220,))
        elif visual == "cup":
            draw.rounded_rectangle((540, 420, 1260, 1220), radius=120, fill=(250, 252, 255, 255), outline=accent + (100,), width=12)
            draw.rounded_rectangle((1170, 570, 1430, 980), radius=100, fill=(240, 246, 255, 255), outline=secondary + (90,), width=10)
        elif visual == "pastry":
            draw.rounded_rectangle((360, 760, 1440, 1160), radius=90, fill=(255, 255, 255, 255), outline=accent + (90,), width=10)
            draw.ellipse((590, 430, 1210, 1030), fill=secondary + (135,), outline=accent + (100,), width=10)
        else:
            draw.rounded_rectangle((420, 420, 1380, 1380), radius=120, fill=(255, 255, 255, 255), outline=accent + (90,), width=10)

        image.save(path, format="PNG", compress_level=1)

    def _background(self, size: tuple[int, int], idx: int):
        image = Image.new("RGBA", size, (244, 247, 251, 255))
        draw = ImageDraw.Draw(image)
        accent = self._accent(idx)
        accent2 = self._accent(idx + 2)
        draw.ellipse((-220, -180, int(size[0] * 0.55), int(size[1] * 0.45)), fill=accent + (34,))
        draw.ellipse((int(size[0] * 0.48), -160, size[0] + 180, int(size[1] * 0.42)), fill=accent2 + (26,))
        draw.rounded_rectangle((90, 90, size[0] - 90, size[1] - 90), radius=110, fill=(255, 255, 255, 150), outline=(255, 255, 255, 90), width=4)
        noise = Image.effect_noise(size, 10).convert("L")
        noise = Image.merge("RGBA", (noise, noise, noise, Image.new("L", size, 18)))
        return Image.alpha_composite(image, noise)

    def _accent(self, idx: int):
        palette = [
            (33, 115, 255),
            (101, 62, 255),
            (24, 195, 255),
            (0, 140, 214),
        ]
        return palette[idx % len(palette)]

    def _public_media_url(self, image_rel: str) -> str:
        configured = getattr(settings, "SERVIO_PUBLIC_BASE_URL", "").strip()
        if configured:
            base = configured.rstrip("/")
        elif settings.DEBUG:
            base = "http://localhost:8080"
        else:
            base = "https://potatofarm.ru"
        return f"{base}/media/{image_rel}"
