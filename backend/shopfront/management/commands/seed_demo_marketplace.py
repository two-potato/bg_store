from __future__ import annotations

import base64
from datetime import timedelta
from decimal import Decimal
from random import Random
from typing import Any

import requests
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from catalog.models import (
    Brand,
    Category,
    Country,
    Product,
    ProductImage,
    ProductQuestion,
    ProductReview,
    ProductReviewComment,
    ProductReviewPhoto,
    ProductReviewVote,
    Series,
    Tag,
)
from commerce.models import (
    ApprovalPolicy,
    Company,
    CompanyContact,
    CompanyMembership,
    LegalEntity,
    LegalEntityMembership,
    MembershipRole,
    SellerStore,
    StoreReview,
)
from shopfront.models import (
    BrandSubscription,
    CategorySubscription,
    FavoriteProduct,
    PersistentCart,
    RecommendationEvent,
    RecentlyViewedProduct,
    SavedSearch,
)
from users.models import UserProfile


TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5+gX8AAAAASUVORK5CYII="
)

TIMEOUT = 8

SELLER_PASSWORD = "ServioSeller123"
BUYER_PASSWORD = "ServioBuyer123"

SELLERS = [
    {
        "username": "seller_demo",
        "full_name": "Анна Воронова",
        "email": "seller_demo@servio.local",
        "phone": "+79001000201",
        "store_name": "Roomers",
        "store_slug": "roomers",
        "store_description": "Подборка посуды, подачи и аксессуаров для ресторанов, отелей и гастробаров.",
        "inn": "500100020201",
        "bik": "044525225",
        "checking_account": "40702810900000000201",
        "brand_focus": "Roomers",
    },
    {
        "username": "seller_costa_porto",
        "full_name": "Мария Дуарте",
        "email": "porto.ceramics@servio.local",
        "phone": "+79001000202",
        "store_name": "Costa Nova Atelier",
        "store_slug": "costa-nova-atelier",
        "store_description": "Керамика для современной сервировки, завтраков, room service и авторской подачи.",
        "inn": "500100020202",
        "bik": "044525225",
        "checking_account": "40702810900000000202",
        "brand_focus": "Costa Nova",
    },
    {
        "username": "seller_glassline",
        "full_name": "Илья Беляев",
        "email": "glassline@servio.local",
        "phone": "+79001000203",
        "store_name": "Glassline Pro",
        "store_slug": "glassline-pro",
        "store_description": "Профессиональное стекло и барные решения для винных карт, коктейльных меню и банкетов.",
        "inn": "500100020203",
        "bik": "044525225",
        "checking_account": "40702810900000000203",
        "brand_focus": "Chef & Sommelier",
    },
    {
        "username": "seller_forma",
        "full_name": "Елизавета Миронова",
        "email": "forma.hub@servio.local",
        "phone": "+79001000204",
        "store_name": "Forma Lab",
        "store_slug": "forma-lab",
        "store_description": "Текстиль, аксессуары для сервировки и тактильные детали для залов и кейтеринга.",
        "inn": "500100020204",
        "bik": "044525225",
        "checking_account": "40702810900000000204",
        "brand_focus": "Nordic Linen",
    },
    {
        "username": "seller_portline",
        "full_name": "Ирина Логинова",
        "email": "portline.store@servio.local",
        "phone": "+79001000205",
        "store_name": "Portline HoReCa",
        "store_slug": "portline-horeca",
        "store_description": "Takeaway, упаковка, GN-гастроемкости и расходники для ежедневной операционной закупки.",
        "inn": "500100020205",
        "bik": "044525225",
        "checking_account": "40702810900000000205",
        "brand_focus": "Portline",
    },
]

BUYERS = [
    ("buyer_iris", "Ирина Мельник", "iris@servio.local"),
    ("buyer_maxim", "Максим Фролов", "maxim@servio.local"),
    ("buyer_daria", "Дарья Крылова", "daria@servio.local"),
    ("buyer_oleg", "Олег Степанов", "oleg@servio.local"),
    ("buyer_yana", "Яна Волкова", "yana@servio.local"),
    ("buyer_timur", "Тимур Романов", "timur@servio.local"),
]

BRANDS = [
    ("Costa Nova", "Португальская керамика для завтраков, room service и стильной подачи."),
    ("Roomers", "Предметы сервировки и подачи для ресторанов и гостиничных проектов."),
    ("Bonna", "Функциональная посуда для интенсивной ресторанной эксплуатации."),
    ("Chef & Sommelier", "Стекло для вина, воды и коктейлей с ресторанной прочностью."),
    ("Nordic Linen", "Текстиль для столов, банкетов и террасной посадки."),
    ("Portline", "Упаковка и сервисные решения для takeaway и dark kitchen форматов."),
]

CATEGORY_TREE = [
    ("tableware", "Посуда и сервировка", None),
    ("plates", "Тарелки", "tableware"),
    ("bowls", "Боулы и салатники", "tableware"),
    ("serving-dishes", "Блюда для подачи", "tableware"),
    ("glassware", "Стекло и бар", None),
    ("wine-glasses", "Бокалы для вина", "glassware"),
    ("tumblers", "Стаканы и тумблеры", "glassware"),
    ("table-linen", "Текстиль", None),
    ("takeaway", "Takeaway и упаковка", None),
    ("kitchen-equipment", "Кухня и гастроемкости", None),
]

COUNTRIES = [
    ("Португалия", "PT"),
    ("Франция", "FR"),
    ("Турция", "TR"),
    ("Италия", "IT"),
    ("Испания", "ES"),
]

TAGS = [
    "restaurant",
    "hotel",
    "banquet",
    "coffee-service",
    "wine-service",
    "buffet",
    "takeaway",
    "handmade",
    "premium",
    "fast-moving",
]

PRODUCT_BLUEPRINTS = [
    ("11000001", "Costa Nova Pearl Dinner Plate 27 cm", "Costa Nova", "Pearl", "plates", "seller_costa_porto", "Португалия", "Керамика", "Подача основных блюд", 1890, 120, 6, 3, True, False, ["restaurant", "premium", "handmade"]),
    ("11000002", "Costa Nova Pearl Side Plate 21 cm", "Costa Nova", "Pearl", "plates", "seller_costa_porto", "Португалия", "Керамика", "Закуски и десерты", 1490, 140, 6, 3, False, True, ["restaurant", "coffee-service", "handmade"]),
    ("11000003", "Costa Nova Brisa Pasta Bowl 24 cm", "Costa Nova", "Brisa", "bowls", "seller_costa_porto", "Португалия", "Керамика", "Паста и салаты", 2090, 85, 4, 4, True, False, ["restaurant", "premium", "buffet"]),
    ("11000004", "Roomers Stone Serving Platter 36 cm", "Roomers", "Stone", "serving-dishes", "seller_demo", "Турция", "Фарфор", "Подача блюд на компанию", 3290, 32, 2, 2, True, False, ["banquet", "restaurant", "premium"]),
    ("11000005", "Roomers Sand Coupe Plate 26 cm", "Roomers", "Sand", "plates", "seller_demo", "Турция", "Фарфор", "Универсальная подача", 1590, 96, 6, 2, False, False, ["restaurant", "hotel", "fast-moving"]),
    ("11000006", "Bonna Aura Bowl 18 cm", "Bonna", "Aura", "bowls", "seller_demo", "Турция", "Фарфор", "Боулы для завтраков и салатов", 1390, 110, 6, 2, False, True, ["hotel", "coffee-service", "fast-moving"]),
    ("11000007", "Bonna Terra Coupe Plate 24 cm", "Bonna", "Terra", "plates", "seller_demo", "Турция", "Фарфор", "Основная посадка и сет-меню", 1790, 90, 6, 3, False, False, ["restaurant", "banquet", "premium"]),
    ("11000008", "Chef Sommelier Open Up Red Wine Glass 470 ml", "Chef & Sommelier", "Open Up", "wine-glasses", "seller_glassline", "Франция", "Стекло", "Красное вино", 990, 180, 12, 2, True, True, ["wine-service", "restaurant", "hotel"]),
    ("11000009", "Chef Sommelier Reveal Up Soft Glass 400 ml", "Chef & Sommelier", "Reveal Up", "wine-glasses", "seller_glassline", "Франция", "Стекло", "Белое и игристое", 1060, 160, 12, 2, False, False, ["wine-service", "banquet", "premium"]),
    ("11000010", "Chef Sommelier Primary Tumbler 350 ml", "Chef & Sommelier", "Primary", "tumblers", "seller_glassline", "Франция", "Стекло", "Вода и коктейли", 760, 210, 12, 1, False, True, ["restaurant", "hotel", "fast-moving"]),
    ("11000011", "Roomers Ribbed Tumbler Smoke 320 ml", "Roomers", "Ribbed", "tumblers", "seller_glassline", "Италия", "Стекло", "Авторские напитки", 890, 150, 12, 3, True, False, ["bar", "restaurant", "premium"]),
    ("11000012", "Nordic Linen Table Runner Sand 180 cm", "Nordic Linen", "Nordic Core", "table-linen", "seller_forma", "Италия", "Лен", "Сервировка столов и банкетов", 2490, 48, 2, 5, True, False, ["banquet", "hotel", "premium"]),
    ("11000013", "Nordic Linen Napkin Clay 45 cm", "Nordic Linen", "Nordic Core", "table-linen", "seller_forma", "Италия", "Лен", "Салфетка для ежедневной сервировки", 690, 240, 12, 4, False, False, ["restaurant", "hotel", "fast-moving"]),
    ("11000014", "Nordic Linen Apron Slate", "Nordic Linen", "Service", "table-linen", "seller_forma", "Испания", "Хлопок", "Форма для сервиса", 2190, 34, 2, 4, False, True, ["restaurant", "hotel", "premium"]),
    ("11000015", "Portline Kraft Bowl 750 ml", "Portline", "Takeaway", "takeaway", "seller_portline", "Турция", "Крафт", "Супы, поке и салаты навынос", 24, 1200, 50, 1, True, False, ["takeaway", "fast-moving", "restaurant"]),
    ("11000016", "Portline Kraft Lid 750 ml", "Portline", "Takeaway", "takeaway", "seller_portline", "Турция", "Крафт", "Крышка к миске 750 мл", 14, 1500, 50, 1, False, False, ["takeaway", "fast-moving", "restaurant"]),
    ("11000017", "Portline Delivery Cup 400 ml", "Portline", "Delivery", "takeaway", "seller_portline", "Турция", "Бумага", "Горячие напитки навынос", 11, 1800, 100, 1, False, True, ["takeaway", "coffee-service", "fast-moving"]),
    ("11000018", "Portline Delivery Cup Lid Black", "Portline", "Delivery", "takeaway", "seller_portline", "Турция", "Пластик", "Крышка для стакана доставки", 8, 2400, 100, 1, False, False, ["takeaway", "coffee-service", "fast-moving"]),
    ("11000019", "Roomers Oval Sharing Plate 31 cm", "Roomers", "Stone", "serving-dishes", "seller_demo", "Турция", "Фарфор", "Блюдо для закусок и sharing sets", 2690, 44, 3, 3, False, False, ["banquet", "restaurant", "premium"]),
    ("11000020", "Bonna Deep Bowl 16 cm", "Bonna", "Aura", "bowls", "seller_demo", "Турция", "Фарфор", "Супы и small plates", 1190, 120, 6, 2, True, False, ["restaurant", "hotel", "fast-moving"]),
    ("11000021", "GN Stainless Pan 1/1 65 mm", "Portline", "Kitchen", "kitchen-equipment", "seller_portline", "Турция", "Нержавеющая сталь", "Линия раздачи и prep station", 1690, 78, 4, 2, False, False, ["buffet", "restaurant", "fast-moving"]),
    ("11000022", "GN Stainless Lid 1/1", "Portline", "Kitchen", "kitchen-equipment", "seller_portline", "Турция", "Нержавеющая сталь", "Крышка для гастроемкости 1/1", 980, 96, 4, 2, False, False, ["buffet", "restaurant", "fast-moving"]),
    ("11000023", "Chef Sommelier Nick Nora Glass 155 ml", "Chef & Sommelier", "Mixology", "tumblers", "seller_glassline", "Франция", "Стекло", "Коктейльная карта и aperitivo", 1120, 95, 12, 2, True, False, ["bar", "restaurant", "premium"]),
    ("11000024", "Costa Nova Notos Oval Bowl 28 cm", "Costa Nova", "Notos", "serving-dishes", "seller_costa_porto", "Португалия", "Керамика", "Овальная подача и sharing plates", 2890, 28, 2, 4, True, False, ["restaurant", "premium", "handmade"]),
]

REVIEW_TEXTS = [
    "Хорошо держит ежедневную нагрузку, выглядит дороже своей цены.",
    "Форма удачная, гости и команда зала постоянно выбирают именно эту позицию.",
    "После нескольких смен сколов не заметили, на выдаче смотрится уверенно.",
    "Отлично встало в нашу подачу завтраков и room service.",
    "Для банкетов удобно: стек и логистика нормальные, вид аккуратный.",
    "Повторно докупили в зал, потому что позиция реально ходовая.",
]

COMMENT_TEXTS = [
    "Подтверждаю, у нас на ежедневной посадке эта серия тоже показала себя отлично.",
    "Согласна, особенно хорошо заходит в сетах с нейтральным текстилем.",
    "У нас по факту еще и поставка пришла быстрее заявленного окна.",
    "Брали под обновление подачи, команда кухни тоже оценила размер и форму.",
]

STORE_REVIEW_TEXTS = [
    "Стабильная коммуникация и понятные сроки отгрузки.",
    "Витрина собрана аккуратно, менеджер быстро помог подобрать замены.",
    "Нравится, что по остаткам и срокам поставщик отвечает честно.",
]

QUESTIONS = [
    ("Подходит ли для интенсивной мойки в посудомоечной машине?", "Да, серия рассчитана на ежедневную эксплуатацию в HoReCa."),
    ("Есть ли коробочные нормы и можно ли брать под банкетную сборку?", "Да, можно, MOQ уже указан в карточке и доступен для смешанных закупок."),
    ("Как ведет себя на room service и завтраках?", "Хорошо: формат удобный для стандартизированной подачи и быстрой комплектации."),
]


class Command(BaseCommand):
    help = "Populate a rich demo marketplace dataset with diverse media, reviews, carts, favorites, and search/recommendation indexing."

    def add_arguments(self, parser):
        parser.add_argument("--skip-indexing", action="store_true", help="Do not reindex search and recommendations after seeding.")

    def handle(self, *args, **options):
        self.rng = Random(20260319)
        self.user_model = get_user_model()
        self.stdout.write("Seeding rich demo marketplace data...")
        with transaction.atomic():
            self._seed_marketplace()
        self.stdout.write(self.style.SUCCESS("Demo marketplace data created/updated."))
        if not options["skip_indexing"]:
            self._refresh_indices()

    def _seed_marketplace(self) -> None:
        self.owner_role, _ = MembershipRole.objects.get_or_create(code="owner", defaults={"name": "Владелец"})
        self.manager_role, _ = MembershipRole.objects.get_or_create(code="manager", defaults={"name": "Менеджер"})
        sellers = self._seed_sellers()
        buyers = self._seed_buyers()
        brands = self._seed_brands()
        categories = self._seed_categories()
        countries = self._seed_countries()
        tags = self._seed_tags()
        series = self._seed_series(brands)
        companies = self._seed_companies(buyers)
        products = self._seed_products(sellers, brands, categories, countries, tags, series)
        self._seed_store_reviews(sellers, buyers)
        self._seed_product_reviews(products, buyers)
        self._seed_questions(products, buyers, sellers)
        self._seed_user_activity(products, buyers, brands, categories)
        self.stdout.write(
            self.style.SUCCESS(
                f"Sellers={len(sellers)} Buyers={len(buyers)} Companies={len(companies)} Brands={len(brands)} Categories={len(categories)} Products={len(products)}"
            )
        )
        self.stdout.write(self.style.WARNING(f"Seller login: seller_demo / {SELLER_PASSWORD}"))
        self.stdout.write(self.style.WARNING(f"Buyer login: {BUYERS[0][0]} / {BUYER_PASSWORD}"))

    def _seed_sellers(self) -> dict[str, Any]:
        sellers: dict[str, Any] = {}
        for index, row in enumerate(SELLERS, start=1):
            user, _ = self.user_model.objects.get_or_create(
                username=row["username"],
                defaults={"email": row["email"], "first_name": row["full_name"].split(" ")[0]},
            )
            user.email = row["email"]
            user.is_active = True
            user.set_password(SELLER_PASSWORD)
            user.save(update_fields=["email", "is_active", "password"])
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.full_name = row["full_name"]
            profile.contact_email = row["email"]
            profile.phone = row["phone"]
            profile.role = UserProfile.Role.SELLER
            self._assign_remote_image(
                profile.photo,
                filename=f"profile_{row['username']}.jpg",
                url=f"https://i.pravatar.cc/512?img={10 + index}",
            )
            profile.save()
            legal_entity, _ = LegalEntity.objects.get_or_create(
                inn=row["inn"],
                defaults={
                    "name": f"ООО {row['store_name']}",
                    "bik": row["bik"],
                    "checking_account": row["checking_account"],
                    "bank_name": "Servio Bank",
                },
            )
            legal_entity.name = f"ООО {row['store_name']}"
            legal_entity.bik = row["bik"]
            legal_entity.checking_account = row["checking_account"]
            legal_entity.bank_name = "Servio Bank"
            legal_entity.save()
            LegalEntityMembership.objects.update_or_create(
                user=user,
                legal_entity=legal_entity,
                defaults={"role": self.owner_role},
            )
            store, _ = SellerStore.objects.get_or_create(
                owner=user,
                defaults={
                    "legal_entity": legal_entity,
                    "name": row["store_name"],
                    "slug": row["store_slug"],
                    "description": row["store_description"],
                },
            )
            store.legal_entity = legal_entity
            store.name = row["store_name"]
            store.slug = row["store_slug"]
            store.description = row["store_description"]
            store.moderation_status = SellerStore.ModerationStatus.APPROVED
            store.is_featured = True
            store.commission_rate = Decimal("9.50")
            self._assign_remote_image(
                store.photo,
                filename=f"store_{row['store_slug']}.jpg",
                url=f"https://picsum.photos/seed/store-{row['store_slug']}/1200/900",
            )
            store.save()
            sellers[row["username"]] = user
        return sellers

    def _seed_buyers(self) -> dict[str, Any]:
        buyers: dict[str, Any] = {}
        for index, (username, full_name, email) in enumerate(BUYERS, start=1):
            user, _ = self.user_model.objects.get_or_create(
                username=username,
                defaults={"email": email, "first_name": full_name.split(" ")[0]},
            )
            user.email = email
            user.is_active = True
            user.set_password(BUYER_PASSWORD)
            user.save(update_fields=["email", "is_active", "password"])
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.full_name = full_name
            profile.contact_email = email
            profile.phone = f"+79003000{index:03d}"
            profile.role = UserProfile.Role.CLIENT
            self._assign_remote_image(
                profile.photo,
                filename=f"profile_{username}.jpg",
                url=f"https://i.pravatar.cc/512?img={30 + index}",
            )
            profile.save()
            buyers[username] = user
        return buyers

    def _seed_brands(self) -> dict[str, Brand]:
        brands: dict[str, Brand] = {}
        for index, (name, description) in enumerate(BRANDS, start=1):
            brand, _ = Brand.objects.get_or_create(name=name)
            brand.description = description
            brand.landing_body = f"{name} в Servio: рабочий ассортимент для закупки залов, баров и кухни."
            brand.faq_title = f"Почему {name} выбирают для HoReCa"
            brand.faq_body = f"{name} подходит для ежедневной эксплуатации, смешанных закупок и обновления сервировочного фонда."
            self._assign_remote_image(
                brand.photo,
                filename=f"brand_{brand.slug or index}.jpg",
                url=f"https://picsum.photos/seed/brand-{index}/1200/900",
            )
            brand.save()
            brands[name] = brand
        return brands

    def _seed_categories(self) -> dict[str, Category]:
        categories: dict[str, Category] = {}
        for index, (slug, name, parent_slug) in enumerate(CATEGORY_TREE, start=1):
            parent = categories.get(parent_slug) if parent_slug else None
            category, _ = Category.objects.get_or_create(slug=slug, defaults={"name": name, "parent": parent})
            category.name = name
            category.parent = parent
            category.description = f"{name} для ресторанов, гостиниц, банкетов и операционных закупок."
            category.hero_title = name
            category.hero_text = f"Подборка Servio: {name.lower()} с понятными MOQ, сроками поставки и витринами продавцов."
            category.landing_body = f"В категории {name.lower()} собраны ходовые позиции для ежедневной работы зала, бара и кухни."
            category.faq_title = f"Как выбирать {name.lower()} в Servio"
            category.faq_body = "Смотрите на материал, минимальную партию, lead time и отзывы команд, которые уже закупали позицию."
            self._assign_remote_image(
                category.photo,
                filename=f"category_{slug}.jpg",
                url=f"https://picsum.photos/seed/category-{slug}/1200/900",
            )
            category.save()
            categories[slug] = category
        return categories

    def _seed_countries(self) -> dict[str, Country]:
        countries: dict[str, Country] = {}
        for name, iso_code in COUNTRIES:
            countries[name], _ = Country.objects.get_or_create(name=name, defaults={"iso_code": iso_code})
        return countries

    def _seed_tags(self) -> dict[str, Tag]:
        tags: dict[str, Tag] = {}
        for name in TAGS:
            tag, _ = Tag.objects.get_or_create(slug=name, defaults={"name": name.replace("-", " ").title()})
            tags[name] = tag
        return tags

    def _seed_series(self, brands: dict[str, Brand]) -> dict[tuple[str, str], Series]:
        series_map: dict[tuple[str, str], Series] = {}
        for _, _, brand_name, series_name, *_ in PRODUCT_BLUEPRINTS:
            key = (brand_name, series_name)
            if key in series_map:
                continue
            series, _ = Series.objects.get_or_create(
                brand=brands[brand_name],
                name=series_name,
                defaults={"description": f"Линейка {series_name} бренда {brand_name}."},
            )
            series.description = f"Линейка {series_name} бренда {brand_name} для закупок HoReCa."
            series.save()
            series_map[key] = series
        return series_map

    def _seed_companies(self, buyers: dict[str, Any]) -> list[Company]:
        companies: list[Company] = []
        company_rows = [
            ("Городской завтрак", "770000000101", "citybreakfast@servio.local", list(buyers.values())[:2]),
            ("Hotel Horizon", "770000000102", "procurement@horizon.local", list(buyers.values())[2:4]),
            ("Bistro Loop", "770000000103", "supply@bistroloop.local", list(buyers.values())[4:]),
        ]
        for index, (display_name, inn, email, members) in enumerate(company_rows, start=1):
            legal_entity, _ = LegalEntity.objects.get_or_create(
                inn=inn,
                defaults={
                    "name": display_name,
                    "bik": "044525225",
                    "checking_account": f"40702810900000010{index:03d}",
                    "bank_name": "Servio Bank",
                },
            )
            legal_entity.name = display_name
            legal_entity.bik = "044525225"
            legal_entity.checking_account = f"40702810900000010{index:03d}"
            legal_entity.bank_name = "Servio Bank"
            legal_entity.save()
            company, _ = Company.objects.get_or_create(legal_entity=legal_entity, defaults={"display_name": display_name})
            company.display_name = display_name
            company.procurement_email = email
            company.procurement_phone = f"+74950000{index:03d}"
            company.invoice_email = f"invoice+{index}@servio.local"
            company.preferred_payment_method = "invoice"
            company.payment_comment = "Отгрузка по будням, приемка с 09:00 до 18:00."
            company.is_active = True
            company.save()
            ApprovalPolicy.objects.update_or_create(
                company=company,
                defaults={
                    "is_enabled": True,
                    "auto_approve_below": Decimal("15000.00"),
                    "require_approver_role": True,
                    "require_comment": False,
                    "required_approvals_count": 1,
                },
            )
            CompanyContact.objects.update_or_create(
                company=company,
                email=email,
                defaults={
                    "name": f"{display_name} закупки",
                    "phone": f"+74951111{index:03d}",
                    "role": CompanyContact.Role.PROCUREMENT,
                    "is_default": True,
                    "notes": "Основной контакт для коммерческих предложений и замены позиций.",
                },
            )
            for member_index, user in enumerate(members):
                CompanyMembership.objects.update_or_create(
                    user=user,
                    company=company,
                    defaults={
                        "role": CompanyMembership.Role.OWNER if member_index == 0 else CompanyMembership.Role.BUYER,
                        "approval_limit": Decimal("50000.00") if member_index == 0 else Decimal("15000.00"),
                        "is_default_approver": member_index == 0,
                    },
                )
                LegalEntityMembership.objects.update_or_create(
                    user=user,
                    legal_entity=legal_entity,
                    defaults={"role": self.manager_role},
                )
            companies.append(company)
        return companies

    def _seed_products(
        self,
        sellers: dict[str, Any],
        brands: dict[str, Brand],
        categories: dict[str, Category],
        countries: dict[str, Country],
        tags: dict[str, Tag],
        series_map: dict[tuple[str, str], Series],
    ) -> list[Product]:
        products: list[Product] = []
        for idx, blueprint in enumerate(PRODUCT_BLUEPRINTS, start=1):
            (
                sku,
                name,
                brand_name,
                series_name,
                category_slug,
                seller_username,
                country_name,
                material,
                purpose,
                price,
                stock_qty,
                min_order_qty,
                lead_time_days,
                is_new,
                is_promo,
                tag_slugs,
            ) = blueprint
            product, _ = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "brand": brands[brand_name],
                    "series": series_map[(brand_name, series_name)],
                    "category": categories[category_slug],
                    "country_of_origin": countries[country_name],
                    "material": material,
                    "purpose": purpose,
                    "price": Decimal(str(price)),
                    "stock_qty": stock_qty,
                    "pack_qty": 1,
                    "unit": "шт",
                    "min_order_qty": min_order_qty,
                    "lead_time_days": lead_time_days,
                    "is_new": is_new,
                    "is_promo": is_promo,
                    "publication_status": Product.PublicationStatus.PUBLISHED,
                    "description": self._product_description(name, purpose, brand_name),
                    "seller": sellers[seller_username],
                },
            )
            product.name = name
            product.brand = brands[brand_name]
            product.series = series_map[(brand_name, series_name)]
            product.category = categories[category_slug]
            product.country_of_origin = countries[country_name]
            product.material = material
            product.purpose = purpose
            product.price = Decimal(str(price))
            product.stock_qty = stock_qty
            product.pack_qty = 1
            product.unit = "шт"
            product.min_order_qty = min_order_qty
            product.lead_time_days = lead_time_days
            product.is_new = is_new
            product.is_promo = is_promo
            product.publication_status = Product.PublicationStatus.PUBLISHED
            product.description = self._product_description(name, purpose, brand_name)
            product.attributes = {
                "usage": purpose,
                "material": material,
                "service_format": "restaurant",
                "segment": "horeca",
            }
            product.composition = material
            product.shelf_life = "Не ограничен при бережной эксплуатации"
            product.seller = sellers[seller_username]
            product.save()
            product.tags.set([tags[tag_slug] for tag_slug in tag_slugs if tag_slug in tags])
            product.images.all().delete()
            for image_index in range(1, 4):
                ProductImage.objects.create(
                    product=product,
                    url=f"https://picsum.photos/seed/product-{sku}-{image_index}/1200/1200",
                    alt=f"{name} photo {image_index}",
                    is_primary=image_index == 1,
                    ordering=image_index,
                )
            products.append(product)
        return products

    def _seed_store_reviews(self, sellers: dict[str, Any], buyers: dict[str, Any]) -> None:
        stores = list(SellerStore.objects.filter(owner__in=sellers.values()).select_related("owner"))
        buyer_list = list(buyers.values())
        for store_index, store in enumerate(stores):
            for offset, review_text in enumerate(STORE_REVIEW_TEXTS):
                user = buyer_list[(store_index + offset) % len(buyer_list)]
                review, _ = StoreReview.objects.get_or_create(
                    store=store,
                    user=user,
                    defaults={
                        "rating": 4 + ((store_index + offset) % 2),
                        "text": review_text,
                        "is_verified_buyer": True,
                    },
                )
                review.rating = 4 + ((store_index + offset) % 2)
                review.text = review_text
                review.is_verified_buyer = True
                review.save()

    def _seed_product_reviews(self, products: list[Product], buyers: dict[str, Any]) -> None:
        buyer_list = list(buyers.values())
        seeded_user_ids = [user.id for user in buyer_list]
        ProductReviewVote.objects.filter(user_id__in=seeded_user_ids).delete()
        ProductReviewComment.objects.filter(user_id__in=seeded_user_ids).delete()
        ProductReviewPhoto.objects.filter(review__user_id__in=seeded_user_ids).delete()
        for index, product in enumerate(products):
            review_count = 2 if index % 3 else 3
            for review_index in range(review_count):
                user = buyer_list[(index + review_index) % len(buyer_list)]
                rating = 5 if (index + review_index) % 4 else 4
                review, _ = ProductReview.objects.get_or_create(
                    product=product,
                    user=user,
                    defaults={
                        "rating": rating,
                        "text": REVIEW_TEXTS[(index + review_index) % len(REVIEW_TEXTS)],
                        "is_verified_purchase": True,
                    },
                )
                review.rating = rating
                review.text = REVIEW_TEXTS[(index + review_index) % len(REVIEW_TEXTS)]
                review.is_verified_purchase = True
                review.save()
                if review_index == 0:
                    ProductReviewPhoto.objects.get_or_create(
                        review=review,
                        ordering=1,
                        defaults={
                            "image_url": f"https://picsum.photos/seed/review-{product.sku}/900/900",
                            "caption": "Фото из реальной эксплуатации",
                        },
                    )
                for comment_index in range(2):
                    commenter = buyer_list[(index + review_index + comment_index + 1) % len(buyer_list)]
                    ProductReviewComment.objects.get_or_create(
                        review=review,
                        user=commenter,
                        text=COMMENT_TEXTS[(index + comment_index) % len(COMMENT_TEXTS)],
                    )
                vote_users = [u for u in buyer_list if u.id != user.id][:3]
                helpful_count = 0
                unhelpful_count = 0
                for vote_index, vote_user in enumerate(vote_users):
                    value = ProductReviewVote.Value.HELPFUL if vote_index < 2 else ProductReviewVote.Value.UNHELPFUL
                    ProductReviewVote.objects.update_or_create(
                        review=review,
                        user=vote_user,
                        defaults={"value": value},
                    )
                    if value == ProductReviewVote.Value.HELPFUL:
                        helpful_count += 1
                    else:
                        unhelpful_count += 1
                review.helpful_count = helpful_count
                review.unhelpful_count = unhelpful_count
                review.save(update_fields=["helpful_count", "unhelpful_count"])

    def _seed_questions(self, products: list[Product], buyers: dict[str, Any], sellers: dict[str, Any]) -> None:
        buyer_list = list(buyers.values())
        seller_list = list(sellers.values())
        for index, product in enumerate(products[:12]):
            question_text, answer_text = QUESTIONS[index % len(QUESTIONS)]
            ProductQuestion.objects.update_or_create(
                product=product,
                user=buyer_list[index % len(buyer_list)],
                question_text=question_text,
                defaults={
                    "answer_text": answer_text,
                    "answered_by": seller_list[index % len(seller_list)],
                    "answered_at": timezone.now() - timedelta(days=index % 5),
                    "is_public": True,
                },
            )

    def _seed_user_activity(
        self,
        products: list[Product],
        buyers: dict[str, Any],
        brands: dict[str, Brand],
        categories: dict[str, Category],
    ) -> None:
        buyer_list = list(buyers.values())
        product_by_index = {index: product for index, product in enumerate(products)}
        FavoriteProduct.objects.filter(user__in=buyer_list).delete()
        BrandSubscription.objects.filter(user__in=buyer_list).delete()
        CategorySubscription.objects.filter(user__in=buyer_list).delete()
        RecentlyViewedProduct.objects.filter(user__in=buyer_list).delete()
        RecommendationEvent.objects.filter(request_id__startswith="seed-demo-").delete()
        for buyer_index, buyer in enumerate(buyer_list):
            favorite_products = [product_by_index[(buyer_index * 3 + step) % len(products)] for step in range(5)]
            for step, product in enumerate(favorite_products):
                favorite = FavoriteProduct.objects.create(user=buyer, product=product)
                FavoriteProduct.objects.filter(pk=favorite.pk).update(created_at=timezone.now() - timedelta(days=step + buyer_index))
            for step, product in enumerate([product_by_index[(buyer_index * 4 + shift) % len(products)] for shift in range(6)]):
                viewed = RecentlyViewedProduct.objects.create(user=buyer, product=product)
                view_time = timezone.now() - timedelta(hours=buyer_index * 2 + step)
                RecentlyViewedProduct.objects.filter(pk=viewed.pk).update(created_at=view_time, updated_at=view_time)
            BrandSubscription.objects.get_or_create(user=buyer, brand=brands[PRODUCT_BLUEPRINTS[buyer_index][2]])
            CategorySubscription.objects.get_or_create(user=buyer, category=categories[PRODUCT_BLUEPRINTS[buyer_index][4]])
            SavedSearch.objects.update_or_create(
                user=buyer,
                name="Закупка недели",
                defaults={"querystring": "q=plate&sort=rating_desc&in_stock=1"},
            )
            cart_products = [product_by_index[(buyer_index * 2 + shift) % len(products)] for shift in range(3)]
            PersistentCart.objects.update_or_create(
                user=buyer,
                defaults={
                    "payload": {
                        str(product.id): {"qty": 1 + ((buyer_index + idx) % 3)}
                        for idx, product in enumerate(cart_products)
                    }
                },
            )
            request_id = f"seed-demo-home-{buyer.id}"
            for position, product in enumerate(cart_products + favorite_products[:2], start=1):
                event_time = timezone.now() - timedelta(hours=position + buyer_index)
                RecommendationEvent.objects.create(
                    event="recommendation_impression",
                    user=buyer,
                    session_key=f"seed-session-{buyer.id}",
                    surface="home",
                    recommendation_source="personalized_home",
                    product=product,
                    seller_id=product.seller_id,
                    brand_id=product.brand_id,
                    category_id=product.category_id,
                    position=position,
                    request_id=request_id,
                    payload={
                        "candidate_sources": ["favorites", "recently_viewed"],
                        "reason_codes": ["seeded_affinity", "demo_personalization"],
                        "model_version": "seed-demo-v1",
                    },
                    created_at=event_time,
                )
                if position <= 3:
                    RecommendationEvent.objects.create(
                        event="recommendation_click",
                        user=buyer,
                        session_key=f"seed-session-{buyer.id}",
                        surface="home",
                        recommendation_source="personalized_home",
                        product=product,
                        seller_id=product.seller_id,
                        brand_id=product.brand_id,
                        category_id=product.category_id,
                        position=position,
                        request_id=request_id,
                        payload={"reason_codes": ["seeded_affinity"], "model_version": "seed-demo-v1"},
                        created_at=event_time + timedelta(minutes=2),
                    )
                if position <= 2:
                    RecommendationEvent.objects.create(
                        event="add_to_cart",
                        user=buyer,
                        session_key=f"seed-session-{buyer.id}",
                        surface="cart",
                        recommendation_source="personalized_home",
                        product=product,
                        seller_id=product.seller_id,
                        brand_id=product.brand_id,
                        category_id=product.category_id,
                        position=position,
                        request_id=request_id,
                        payload={"line_value": float(product.price), "model_version": "seed-demo-v1"},
                        created_at=event_time + timedelta(minutes=3),
                    )

    def _refresh_indices(self) -> None:
        self.stdout.write("Reindexing OpenSearch products...")
        try:
            call_command("reindex_products_search")
            self.stdout.write(self.style.SUCCESS("Search index refreshed."))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"Search reindex skipped/failed: {exc}"))
        self.stdout.write("Refreshing recommendation snapshots...")
        try:
            call_command("refresh_recommendations", window="30d", limit=80, set_limit=12)
            self.stdout.write(self.style.SUCCESS("Recommendation snapshots refreshed."))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"Recommendation refresh skipped/failed: {exc}"))

    def _product_description(self, name: str, purpose: str, brand_name: str) -> str:
        return (
            f"{name} от {brand_name} для сценария «{purpose.lower()}». "
            "Позиция добавлена в демо-каталог Servio с понятным MOQ, остатками и витриной продавца."
        )

    def _assign_remote_image(self, field_file, *, filename: str, url: str) -> None:
        content = self._download_image(url)
        field_file.save(filename, ContentFile(content), save=False)

    def _download_image(self, url: str) -> bytes:
        try:
            response = requests.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            return response.content
        except Exception:
            return TINY_PNG
