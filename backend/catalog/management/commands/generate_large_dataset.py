from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from catalog.models import (
    Brand,
    Category,
    Color,
    Country,
    Product,
    ProductImage,
    Series,
    Tag,
)
from commerce.models import DeliveryAddress, LegalEntity, LegalEntityMembership, MembershipRole
from users.models import User, UserProfile


def _digits_checksum(nums: str, coeffs: list[int]) -> str:
    total = sum(int(a) * b for a, b in zip(nums, coeffs))
    return str((total % 11) % 10)


def _build_valid_inn10(base9: str) -> str:
    return base9 + _digits_checksum(base9, [2, 4, 10, 3, 5, 9, 4, 6, 8])


def _rs_control_ok(rs: str, bik: str) -> bool:
    control_str = bik[-3:] + rs
    weights = ([7, 3, 1] * 8) + [7]
    return (sum(int(d) * weights[i] for i, d in enumerate(control_str)) % 10) == 0


def _build_valid_checking_account(bik: str, seed: int) -> str:
    base19 = f"40702810{seed:011d}"[-19:]
    for last in range(10):
        candidate = base19 + str(last)
        if _rs_control_ok(candidate, bik):
            return candidate
    raise RuntimeError("Cannot build valid checking account")


def _ensure_users_profiles_filled() -> None:
    now_ts = int(timezone.now().timestamp())
    profiles = UserProfile.objects.select_related("user").all()
    updates: list[UserProfile] = []
    for p in profiles:
        u = p.user
        changed = False
        if not p.full_name.strip():
            p.full_name = (u.get_full_name() or u.username or "").strip()
            changed = True
        if not (p.contact_email or "").strip():
            p.contact_email = (u.email or f"{u.username}@example.test").strip()
            changed = True
        if not (p.phone or "").strip():
            p.phone = f"+7999{(u.id or 0):07d}"[:12]
            changed = True
        if p.telegram_id is None:
            p.telegram_id = now_ts * 100000 + (u.id or 0)
            changed = True
        if not (p.telegram_username or "").strip():
            p.telegram_username = f"tg_{u.username}"[:255]
            changed = True
        if p.discount is None:
            p.discount = Decimal("0.00")
            changed = True
        if not p.role:
            p.role = UserProfile.Role.CLIENT
            changed = True
        if changed:
            updates.append(p)
    if updates:
        UserProfile.objects.bulk_update(
            updates,
            fields=[
                "full_name",
                "contact_email",
                "phone",
                "telegram_id",
                "telegram_username",
                "discount",
                "role",
            ],
            batch_size=1000,
        )


@dataclass
class Target:
    users_add: int
    categories_total: int
    tags_total: int
    products_total: int
    orgs_total: int
    addresses_total: int


class Command(BaseCommand):
    help = "Generate a large deterministic demo dataset"

    def add_arguments(self, parser):
        parser.add_argument("--users-add", type=int, default=200)
        parser.add_argument("--categories-total", type=int, default=350)
        parser.add_argument("--tags-total", type=int, default=1500)
        parser.add_argument("--products-total", type=int, default=6000)
        parser.add_argument("--orgs-total", type=int, default=150)
        parser.add_argument("--addresses-total", type=int, default=500)
        parser.add_argument("--assign-ratio", type=float, default=0.95)

    @transaction.atomic
    def handle(self, *args, **options):
        target = Target(
            users_add=options["users_add"],
            categories_total=options["categories_total"],
            tags_total=options["tags_total"],
            products_total=options["products_total"],
            orgs_total=options["orgs_total"],
            addresses_total=options["addresses_total"],
        )
        assign_ratio = float(options["assign_ratio"])

        manager_role, _ = MembershipRole.objects.get_or_create(
            code="manager",
            defaults={"name": "Менеджер"},
        )

        self._create_users(target.users_add)
        _ensure_users_profiles_filled()
        self._create_organizations(target.orgs_total)
        self._create_addresses(target.addresses_total)
        self._assign_organizations_to_users(assign_ratio, manager_role)
        self._ensure_catalog_lookups()
        self._create_categories(target.categories_total)
        self._create_tags(target.tags_total)
        self._create_products(target.products_total)
        self._assign_tags_to_products()
        self._ensure_three_photos_per_product()

        counts = {
            "users": User.objects.count(),
            "profiles": UserProfile.objects.count(),
            "categories": Category.objects.count(),
            "tags": Tag.objects.count(),
            "products": Product.objects.count(),
            "orgs": LegalEntity.objects.count(),
            "addresses": DeliveryAddress.objects.count(),
            "memberships": LegalEntityMembership.objects.count(),
            "product_images": ProductImage.objects.count(),
        }
        self.stdout.write(self.style.SUCCESS(f"Dataset ready: {counts}"))

    def _create_users(self, add_count: int) -> None:
        if add_count <= 0:
            return
        start = User.objects.filter(username__startswith="load_user_").count() + 1
        to_create: list[User] = []
        pwd = make_password("LoadTest!123")
        for i in range(start, start + add_count):
            username = f"load_user_{i:05d}"
            to_create.append(
                User(
                    username=username,
                    first_name=f"Load{i:05d}",
                    last_name="User",
                    email=f"{username}@example.test",
                    is_active=True,
                    password=pwd,
                )
            )
        User.objects.bulk_create(to_create, batch_size=1000)

        created = list(User.objects.filter(username__startswith="load_user_").order_by("-id")[:add_count])
        now_ts = int(timezone.now().timestamp())
        profiles = [
            UserProfile(
                user=u,
                full_name=f"{u.first_name} {u.last_name}".strip(),
                contact_email=u.email or "",
                phone=f"+7999{u.id:07d}"[:12],
                telegram_id=now_ts * 100000 + u.id,
                telegram_username=f"tg_{u.username}"[:255],
                discount=Decimal("3.00"),
                role=UserProfile.Role.CLIENT,
            )
            for u in created
        ]
        existing_profile_user_ids = set(
            UserProfile.objects.filter(user_id__in=[u.id for u in created]).values_list("user_id", flat=True)
        )
        profiles = [p for p in profiles if p.user_id not in existing_profile_user_ids]
        if profiles:
            UserProfile.objects.bulk_create(profiles, batch_size=1000)

    def _create_organizations(self, target_total: int) -> None:
        missing = max(0, target_total - LegalEntity.objects.count())
        if missing == 0:
            return
        start = LegalEntity.objects.filter(name__startswith="Load Org ").count() + 1
        entities: list[LegalEntity] = []
        existing_inn = set(LegalEntity.objects.values_list("inn", flat=True))
        seq = 100_000_000
        for i in range(start, start + missing):
            while True:
                base9 = f"{seq:09d}"[-9:]
                inn = _build_valid_inn10(base9)
                seq += 1
                if inn not in existing_inn:
                    existing_inn.add(inn)
                    break
            bik = f"044525{i % 1000:03d}"
            checking_account = _build_valid_checking_account(bik, i)
            entities.append(
                LegalEntity(
                    name=f"Load Org {i:04d}",
                    inn=inn,
                    bik=bik,
                    checking_account=checking_account,
                    bank_name=f"Test Bank {i:03d}",
                )
            )
        LegalEntity.objects.bulk_create(entities, batch_size=500)

    def _create_addresses(self, target_total: int) -> None:
        missing = max(0, target_total - DeliveryAddress.objects.count())
        if missing == 0:
            return
        org_ids = list(LegalEntity.objects.order_by("id").values_list("id", flat=True))
        if not org_ids:
            return
        start = DeliveryAddress.objects.filter(label__startswith="Load Address ").count() + 1
        to_create: list[DeliveryAddress] = []
        for i in range(start, start + missing):
            org_id = org_ids[(i - start) % len(org_ids)]
            to_create.append(
                DeliveryAddress(
                    legal_entity_id=org_id,
                    label=f"Load Address {i:05d}",
                    country="Россия",
                    city=f"Город {i % 120:03d}",
                    street=f"Улица Нагрузки, д. {i % 300 + 1}",
                    postcode=f"{100000 + (i % 899999):06d}",
                    details=f"Подъезд {i % 8 + 1}, этаж {i % 25 + 1}",
                    latitude=Decimal("55.750000") + Decimal(i % 1000) / Decimal("100000"),
                    longitude=Decimal("37.620000") + Decimal(i % 1000) / Decimal("100000"),
                    is_default=(i % 17 == 0),
                )
            )
        DeliveryAddress.objects.bulk_create(to_create, batch_size=1000)

    def _assign_organizations_to_users(self, ratio: float, role: MembershipRole) -> None:
        users = list(User.objects.order_by("id").values_list("id", flat=True))
        orgs = list(LegalEntity.objects.order_by("id").values_list("id", flat=True))
        if not users or not orgs:
            return
        target_users = int(len(users) * ratio)
        chosen_user_ids = users[:target_users]
        users_with_membership = set(
            LegalEntityMembership.objects.filter(user_id__in=chosen_user_ids).values_list("user_id", flat=True)
        )
        to_create: list[LegalEntityMembership] = []
        org_len = len(orgs)
        for idx, user_id in enumerate(chosen_user_ids):
            if user_id in users_with_membership:
                continue
            org_id = orgs[idx % org_len]
            to_create.append(
                LegalEntityMembership(
                    user_id=user_id,
                    legal_entity_id=org_id,
                    role_id=role.id,
                )
            )
        if to_create:
            LegalEntityMembership.objects.bulk_create(to_create, batch_size=1000)

    def _ensure_catalog_lookups(self) -> None:
        if Brand.objects.count() < 20:
            missing = 20 - Brand.objects.count()
            start = Brand.objects.filter(name__startswith="Load Brand ").count() + 1
            Brand.objects.bulk_create(
                [
                    Brand(
                        name=f"Load Brand {i:03d}",
                        description=f"Бренд для нагрузки {i:03d}",
                        meta_title=f"Load Brand {i:03d}",
                        meta_description=f"Описание бренда {i:03d}",
                        meta_keywords=f"load,brand,{i:03d}",
                    )
                    for i in range(start, start + missing)
                ],
                batch_size=500,
            )

        if Country.objects.count() < 20:
            missing = 20 - Country.objects.count()
            start = Country.objects.filter(name__startswith="Load Country ").count() + 1
            Country.objects.bulk_create(
                [
                    Country(
                        name=f"Load Country {i:03d}",
                        iso_code=f"L{i:02d}"[-3:],
                    )
                    for i in range(start, start + missing)
                ],
                batch_size=200,
            )

        if Color.objects.count() < 20:
            missing = 20 - Color.objects.count()
            start = Color.objects.filter(name__startswith="Load Color ").count() + 1
            Color.objects.bulk_create(
                [
                    Color(name=f"Load Color {i:03d}", hex_code=f"#{(i * 123457) % 0xFFFFFF:06X}")
                    for i in range(start, start + missing)
                ],
                batch_size=200,
            )

        brands = list(Brand.objects.order_by("id"))
        if Series.objects.count() < 80 and brands:
            missing = 80 - Series.objects.count()
            start = Series.objects.filter(name__startswith="Load Series ").count() + 1
            rows: list[Series] = []
            for i in range(start, start + missing):
                brand = brands[(i - start) % len(brands)]
                rows.append(
                    Series(
                        brand_id=brand.id,
                        name=f"Load Series {i:04d}",
                        description=f"Серия для нагрузки {i:04d}",
                        meta_title=f"Load Series {i:04d}",
                        meta_description=f"Описание серии {i:04d}",
                        meta_keywords=f"load,series,{i:04d}",
                    )
                )
            Series.objects.bulk_create(rows, batch_size=500)

    def _create_categories(self, target_total: int) -> None:
        missing = max(0, target_total - Category.objects.count())
        if missing == 0:
            return
        start = Category.objects.filter(name__startswith="Load Category ").count() + 1
        existing = list(Category.objects.order_by("id").values_list("id", flat=True))
        to_create: list[Category] = []
        for i in range(start, start + missing):
            parent_id = None
            if existing and (i % 4 == 0):
                parent_id = existing[i % len(existing)]
            to_create.append(
                Category(
                    name=f"Load Category {i:04d}",
                    slug=f"load-category-{i:04d}",
                    parent_id=parent_id,
                    description=f"Полное описание категории {i:04d}",
                    meta_title=f"Категория {i:04d}",
                    meta_description=f"SEO описание категории {i:04d}",
                    meta_keywords=f"load,category,{i:04d}",
                )
            )
        Category.objects.bulk_create(to_create, batch_size=1000)

    def _create_tags(self, target_total: int) -> None:
        missing = max(0, target_total - Tag.objects.count())
        if missing == 0:
            return
        start = Tag.objects.filter(name__startswith="Load Tag ").count() + 1
        Tag.objects.bulk_create(
            [
                Tag(name=f"Load Tag {i:05d}", slug=f"load-tag-{i:05d}")
                for i in range(start, start + missing)
            ],
            batch_size=2000,
        )

    def _create_products(self, target_total: int) -> None:
        missing = max(0, target_total - Product.objects.count())
        if missing == 0:
            return
        brand_ids = list(Brand.objects.order_by("id").values_list("id", flat=True))
        series_ids = list(Series.objects.order_by("id").values_list("id", flat=True))
        category_ids = list(Category.objects.order_by("id").values_list("id", flat=True))
        country_ids = list(Country.objects.order_by("id").values_list("id", flat=True))
        color_ids = list(Color.objects.order_by("id").values_list("id", flat=True))

        if not (brand_ids and series_ids and category_ids and country_ids and color_ids):
            raise RuntimeError("Catalog lookups are not ready")

        existing_skus = set(Product.objects.values_list("sku", flat=True))
        start_num = 20_000_000
        rows: list[Product] = []
        created = 0
        cursor = start_num
        while created < missing:
            sku = f"{cursor:08d}"
            cursor += 1
            if sku in existing_skus:
                continue
            existing_skus.add(sku)
            idx = created
            rows.append(
                Product(
                    sku=sku,
                    manufacturer_sku=f"MSKU-{sku}",
                    name=f"Load Product {sku}",
                    slug=f"load-product-{sku}",
                    brand_id=brand_ids[idx % len(brand_ids)],
                    series_id=series_ids[idx % len(series_ids)],
                    category_id=category_ids[idx % len(category_ids)],
                    country_of_origin_id=country_ids[idx % len(country_ids)],
                    material=f"Материал {idx % 50 + 1}",
                    purpose=f"Назначение товара {idx % 100 + 1}",
                    color_id=color_ids[idx % len(color_ids)],
                    flavor=f"Вкус {idx % 80 + 1}",
                    diameter_mm=Decimal("65.00") + Decimal(idx % 15),
                    height_mm=Decimal("120.00") + Decimal(idx % 100),
                    length_mm=Decimal("80.00") + Decimal(idx % 60),
                    width_mm=Decimal("40.00") + Decimal(idx % 50),
                    volume_ml=Decimal("250.00") + Decimal((idx % 8) * 50),
                    weight_g=Decimal("200.00") + Decimal((idx % 20) * 25),
                    pack_qty=(idx % 24) + 1,
                    unit="шт",
                    barcode=f"460{sku}{idx % 10}",
                    price=Decimal("99.00") + Decimal((idx % 3000) / 10),
                    stock_qty=(idx % 500) + 20,
                    is_new=(idx % 11 == 0),
                    is_promo=(idx % 7 == 0),
                    attributes={
                        "strength": idx % 10,
                        "line": f"L{idx % 40:02d}",
                        "temperature": 20 + (idx % 15),
                    },
                    composition=f"Состав товара {sku}: ингредиенты и материалы.",
                    shelf_life=f"{12 + (idx % 24)} месяцев",
                    description=f"Полное описание товара {sku}. Подходит для нагрузочного теста каталога и заказов.",
                    meta_title=f"SEO {sku}",
                    meta_description=f"SEO описание товара {sku}",
                    meta_keywords=f"load,product,{sku}",
                )
            )
            created += 1
        Product.objects.bulk_create(rows, batch_size=1000)

    def _assign_tags_to_products(self) -> None:
        through = Product.tags.through
        tag_ids = list(Tag.objects.order_by("id").values_list("id", flat=True))
        if not tag_ids:
            return
        existing_rel = set(
            through.objects.values_list("product_id", "tag_id")
        )
        products = Product.objects.order_by("id").values_list("id", flat=True)
        to_create = []
        tlen = len(tag_ids)
        for idx, pid in enumerate(products):
            rels = [
                (pid, tag_ids[(idx * 3) % tlen]),
                (pid, tag_ids[(idx * 3 + 1) % tlen]),
                (pid, tag_ids[(idx * 3 + 2) % tlen]),
            ]
            for pair in rels:
                if pair in existing_rel:
                    continue
                existing_rel.add(pair)
                to_create.append(through(product_id=pair[0], tag_id=pair[1]))
        if to_create:
            through.objects.bulk_create(to_create, batch_size=5000)

    def _ensure_three_photos_per_product(self) -> None:
        image_ids_to_delete = []
        images_by_product: dict[int, list[dict]] = {}
        for row in ProductImage.objects.order_by("product_id", "ordering", "id").values(
            "id", "product_id", "ordering", "is_primary", "alt", "url"
        ):
            images_by_product.setdefault(row["product_id"], []).append(row)

        to_update: list[ProductImage] = []
        to_create: list[ProductImage] = []
        for pid, name in Product.objects.values_list("id", "name"):
            current = images_by_product.get(pid, [])
            keep = current[:3]
            drop = current[3:]
            image_ids_to_delete.extend([img["id"] for img in drop])
            for pos, img in enumerate(keep):
                changed = False
                if img["ordering"] != pos:
                    changed = True
                if img["is_primary"] != (pos == 0):
                    changed = True
                expected_alt = name[:255]
                if (img["alt"] or "") != expected_alt:
                    changed = True
                if changed:
                    to_update.append(
                        ProductImage(
                            id=img["id"],
                            product_id=pid,
                            ordering=pos,
                            is_primary=(pos == 0),
                            alt=expected_alt,
                            url=img["url"],
                        )
                    )
            if len(keep) < 3:
                for pos in range(len(keep), 3):
                    to_create.append(
                        ProductImage(
                            product_id=pid,
                            url=f"https://picsum.photos/seed/product-{pid}-{pos + 1}/1200/900",
                            alt=name[:255],
                            is_primary=(pos == 0 and len(keep) == 0),
                            ordering=pos,
                        )
                    )

        if image_ids_to_delete:
            ProductImage.objects.filter(id__in=image_ids_to_delete).delete()
        if to_update:
            ProductImage.objects.bulk_update(to_update, fields=["ordering", "is_primary", "alt"], batch_size=5000)
        if to_create:
            ProductImage.objects.bulk_create(to_create, batch_size=5000)

        # Guardrail: every product must have exactly 3 images.
        bad = (
            Product.objects.annotate(img_count=Count("images"))
            .exclude(img_count=3)
            .values_list("id", "img_count")[:5]
        )
        if bad:
            raise RuntimeError(f"Products without exactly 3 images: {list(bad)}")
