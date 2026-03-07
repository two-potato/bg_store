from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Brand, Category, Color, Country, Product, Series, Tag
from commerce.models import DeliveryAddress, LegalEntity
from users.models import User, UserProfile


FIRST_NAMES = [
    "Лев",
    "Тимур",
    "Марк",
    "Мирон",
    "Глеб",
    "Арсений",
    "Роман",
    "Даниил",
    "Никита",
    "Ярослав",
    "Павел",
    "Дамир",
]

LAST_NAMES = [
    "Северин",
    "Ладожский",
    "Ветров",
    "Яхонтов",
    "Орлов",
    "Соколин",
    "Громов",
    "Тернов",
    "Вольский",
    "Малинов",
    "Берестов",
    "Озерский",
]

EPITHETS = [
    "Аврора",
    "Сапфир",
    "Мистраль",
    "Лаванда",
    "Янтарь",
    "Оникс",
    "Вереск",
    "Бриз",
    "Каскад",
    "Рубин",
    "Гранат",
    "Иней",
]

NOUNS = [
    "Маркет",
    "Палитра",
    "Коллекция",
    "Ателье",
    "Союз",
    "Линия",
    "Мануфактура",
    "Двор",
    "Порт",
    "Дом",
    "Склад",
    "Квартал",
]

PRODUCT_LINES = [
    "Ночная Смена",
    "Тёплый Свет",
    "Пыльца Ветра",
    "Линия Север",
    "Третий Рассвет",
    "Мягкий Контур",
    "Сад Фонарей",
    "Серебряный Пик",
    "Кофейный Ритм",
    "Город у Моря",
    "Вечерний Пирс",
    "Полярная Полка",
]

TAG_WORDS = [
    "бархат",
    "искры",
    "бриз",
    "цитрус",
    "карамель",
    "миндаль",
    "ритм",
    "утро",
    "север",
    "мираж",
    "неон",
    "тепло",
    "каскад",
    "атлас",
    "орбита",
]

CITY_NAMES = [
    "Светлогорск",
    "Лазурск",
    "Сосново",
    "Бризово",
    "Северодом",
    "Янтарино",
    "Винтажск",
    "Озерки",
    "Рассветное",
    "Гармонино",
]

STREET_NAMES = [
    "Аллея Тёплых Огней",
    "Проспект Лунного Кофе",
    "Улица Янтарных Витрин",
    "Набережная Вечернего Света",
    "Проезд Сапфировых Теней",
    "Бульвар Мягкого Ритма",
    "Переулок Бархатных Ароматов",
    "Тракт Северного Бриза",
]


class Command(BaseCommand):
    help = "Rename generated Load* dataset records with original and красивыми названиями"

    @transaction.atomic
    def handle(self, *args, **options):
        self._beautify_users()
        self._beautify_orgs_and_addresses()
        self._beautify_catalog()
        self.stdout.write(self.style.SUCCESS("Beautified generated dataset names"))

    def _beautify_users(self) -> None:
        users = list(User.objects.filter(username__startswith="load_user_").order_by("id"))
        if not users:
            return
        user_updates = []
        profile_updates = []
        for idx, user in enumerate(users):
            first = FIRST_NAMES[idx % len(FIRST_NAMES)]
            last = LAST_NAMES[(idx // len(FIRST_NAMES)) % len(LAST_NAMES)]
            stage = (idx % 97) + 1
            user.first_name = first
            user.last_name = last
            user.email = f"{user.username}@aurora-mail.test"
            user_updates.append(user)

            profile = UserProfile.objects.filter(user_id=user.id).first()
            if profile:
                profile.full_name = f"{first} {last}"
                profile.contact_email = user.email
                profile.telegram_username = f"{first.lower()}_{last.lower()}_{stage}".replace(" ", "_")[:255]
                profile_updates.append(profile)

        User.objects.bulk_update(user_updates, ["first_name", "last_name", "email"], batch_size=1000)
        if profile_updates:
            UserProfile.objects.bulk_update(
                profile_updates,
                ["full_name", "contact_email", "telegram_username"],
                batch_size=1000,
            )

    def _beautify_orgs_and_addresses(self) -> None:
        orgs = list(LegalEntity.objects.filter(name__startswith="Load Org ").order_by("id"))
        org_updates = []
        for idx, org in enumerate(orgs):
            name = f"{EPITHETS[idx % len(EPITHETS)]} {NOUNS[idx % len(NOUNS)]} {idx + 1:03d}"
            org.name = name
            if not (org.bank_name or "").strip():
                org.bank_name = f"Банк «{EPITHETS[(idx + 3) % len(EPITHETS)]}»"
            org_updates.append(org)
        if org_updates:
            LegalEntity.objects.bulk_update(org_updates, ["name", "bank_name"], batch_size=1000)

        addrs = list(DeliveryAddress.objects.filter(label__startswith="Load Address ").order_by("id"))
        addr_updates = []
        for idx, addr in enumerate(addrs):
            city = CITY_NAMES[idx % len(CITY_NAMES)]
            street = STREET_NAMES[idx % len(STREET_NAMES)]
            addr.label = f"Склад «{EPITHETS[idx % len(EPITHETS)]}» {idx + 1:03d}"
            addr.city = city
            addr.street = f"{street}, д. {idx % 240 + 1}"
            addr.details = f"Секция {idx % 12 + 1}, рампа {idx % 8 + 1}"
            addr_updates.append(addr)
        if addr_updates:
            DeliveryAddress.objects.bulk_update(addr_updates, ["label", "city", "street", "details"], batch_size=1000)

    def _beautify_catalog(self) -> None:
        brands = list(Brand.objects.filter(name__startswith="Load Brand ").order_by("id"))
        b_updates = []
        for idx, brand in enumerate(brands):
            brand.name = f"{EPITHETS[idx % len(EPITHETS)]} Atelier {idx + 1:03d}"
            brand.description = f"Лимитированная линейка бренда {brand.name}"
            brand.meta_title = brand.name
            brand.meta_description = f"Каталог бренда {brand.name}"
            brand.meta_keywords = f"brand,{idx + 1},original"
            b_updates.append(brand)
        if b_updates:
            Brand.objects.bulk_update(
                b_updates,
                ["name", "description", "meta_title", "meta_description", "meta_keywords"],
                batch_size=500,
            )

        series = list(Series.objects.filter(name__startswith="Load Series ").order_by("id"))
        s_updates = []
        for idx, row in enumerate(series):
            row.name = f"Серия {PRODUCT_LINES[idx % len(PRODUCT_LINES)]} {idx + 1:03d}"
            row.description = f"Товарная серия с акцентом на стиль и стабильность: {row.name}"
            row.meta_title = row.name
            row.meta_description = f"SEO описание серии {row.name}"
            row.meta_keywords = f"series,{idx + 1},collection"
            s_updates.append(row)
        if s_updates:
            Series.objects.bulk_update(
                s_updates,
                ["name", "description", "meta_title", "meta_description", "meta_keywords"],
                batch_size=500,
            )

        countries = list(Country.objects.filter(name__startswith="Load Country ").order_by("id"))
        c_updates = []
        for idx, country in enumerate(countries):
            country.name = f"Аркадия {idx + 1:02d}"
            c_updates.append(country)
        if c_updates:
            Country.objects.bulk_update(c_updates, ["name"], batch_size=200)

        colors = list(Color.objects.filter(name__startswith="Load Color ").order_by("id"))
        clr_updates = []
        for idx, color in enumerate(colors):
            color.name = f"{EPITHETS[idx % len(EPITHETS)]} Тон {idx + 1:02d}"
            clr_updates.append(color)
        if clr_updates:
            Color.objects.bulk_update(clr_updates, ["name"], batch_size=200)

        cats = list(Category.objects.filter(name__startswith="Load Category ").order_by("id"))
        cat_updates = []
        for idx, cat in enumerate(cats):
            cat.name = f"{EPITHETS[idx % len(EPITHETS)]} {NOUNS[idx % len(NOUNS)]} {idx + 1:03d}"
            cat.slug = f"poetic-category-{idx + 1:04d}"
            cat.description = f"Эстетичная категория для витрины: {cat.name}"
            cat.meta_title = cat.name
            cat.meta_description = f"SEO описание категории {cat.name}"
            cat.meta_keywords = f"category,{idx + 1},poetic"
            cat_updates.append(cat)
        if cat_updates:
            Category.objects.bulk_update(
                cat_updates,
                ["name", "slug", "description", "meta_title", "meta_description", "meta_keywords"],
                batch_size=1000,
            )

        tags = list(Tag.objects.filter(name__startswith="Load Tag ").order_by("id"))
        tag_updates = []
        for idx, tag in enumerate(tags):
            word = TAG_WORDS[idx % len(TAG_WORDS)]
            tag.name = f"{word}-{idx + 1:04d}"
            tag.slug = f"poetic-tag-{idx + 1:04d}"
            tag_updates.append(tag)
        if tag_updates:
            Tag.objects.bulk_update(tag_updates, ["name", "slug"], batch_size=2000)

        products = list(Product.objects.filter(name__startswith="Load Product ").order_by("id"))
        p_updates = []
        for idx, p in enumerate(products):
            line = PRODUCT_LINES[idx % len(PRODUCT_LINES)]
            edition = EPITHETS[(idx // len(PRODUCT_LINES)) % len(EPITHETS)]
            p.name = f"{line} «{edition}» {idx + 1:04d}"
            p.slug = f"poetic-product-{p.sku}"
            p.description = (
                f"{p.name} — выразительная позиция ассортимента с детально заполненными характеристиками. "
                "Создано для красивой и реалистичной демо-витрины."
            )
            p.meta_title = p.name
            p.meta_description = f"SEO описание товара {p.name}"
            p.meta_keywords = f"product,{p.sku},poetic"
            p_updates.append(p)
        if p_updates:
            Product.objects.bulk_update(
                p_updates,
                ["name", "slug", "description", "meta_title", "meta_description", "meta_keywords"],
                batch_size=1000,
            )
