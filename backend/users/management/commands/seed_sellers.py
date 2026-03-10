import base64
from itertools import cycle

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from catalog.models import Product
from commerce.models import LegalEntity, LegalEntityMembership, MembershipRole, SellerStore
from users.models import UserProfile


TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5+gX8AAAAASUVORK5CYII="
)


class Command(BaseCommand):
    help = "Create 5 seller users with full profiles, stores, avatars and assign all products to sellers."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="SellerPass!2026", help="Password for all seeded sellers.")

    def handle(self, *args, **options):
        password = options["password"]
        User = get_user_model()

        seed_data = [
            {
                "username": "seller_servio_central",
                "full_name": "Марина Соколова",
                "email": "central.supply@servio.local",
                "phone": "+79001000101",
                "store_name": "Servio Central Supply",
                "store_description": "Витрина базового ассортимента для кухни, зала и сервисных закупок HoReCa.",
                "inn": "500100010101",
                "bik": "044525225",
                "checking_account": "40702810900000000101",
            },
            {
                "username": "seller_northline",
                "full_name": "Артем Корнеев",
                "email": "northline.pro@servio.local",
                "phone": "+79001000102",
                "store_name": "Northline Pro Store",
                "store_description": "Поставщик сервировочной посуды, стекла и решений для стабильной операционной закупки.",
                "inn": "500100010102",
                "bik": "044525225",
                "checking_account": "40702810900000000102",
            },
            {
                "username": "seller_forma",
                "full_name": "Елизавета Миронова",
                "email": "forma.hub@servio.local",
                "phone": "+79001000103",
                "store_name": "Forma HoReCa Hub",
                "store_description": "Каталог текстиля, подачи и инвентаря для ресторанов, кафе и гостиничных объектов.",
                "inn": "500100010103",
                "bik": "044525225",
                "checking_account": "40702810900000000103",
            },
            {
                "username": "seller_aurum",
                "full_name": "Денис Павлов",
                "email": "aurum.market@servio.local",
                "phone": "+79001000104",
                "store_name": "Aurum Kitchen Market",
                "store_description": "Поставщик профессиональной кухни, гастроёмкостей и рабочих форматов для back-of-house.",
                "inn": "500100010104",
                "bik": "044525225",
                "checking_account": "40702810900000000104",
            },
            {
                "username": "seller_portline",
                "full_name": "Ирина Логинова",
                "email": "portline.store@servio.local",
                "phone": "+79001000105",
                "store_name": "Portline HoReCa Store",
                "store_description": "Ассортимент упаковки, takeaway и расходных материалов для регулярной сервисной работы.",
                "inn": "500100010105",
                "bik": "044525225",
                "checking_account": "40702810900000000105",
            },
        ]

        owner_role, _ = MembershipRole.objects.get_or_create(code="owner", defaults={"name": "Владелец"})
        sellers = []

        for idx, row in enumerate(seed_data, start=1):
            user, _ = User.objects.get_or_create(
                username=row["username"],
                defaults={"email": row["email"], "first_name": row["full_name"].split(" ")[0]},
            )
            user.email = row["email"]
            user.set_password(password)
            user.is_active = True
            user.save(update_fields=["email", "password", "is_active"])

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.full_name = row["full_name"]
            profile.contact_email = row["email"]
            profile.phone = row["phone"]
            profile.role = UserProfile.Role.SELLER
            profile.photo.save(f"seller_profile_{idx}.png", ContentFile(TINY_PNG), save=False)
            profile.save()

            legal_entity, _ = LegalEntity.objects.get_or_create(
                inn=row["inn"],
                defaults={
                    "name": f"Юрлицо {row['store_name']}",
                    "bik": row["bik"],
                    "checking_account": row["checking_account"],
                    "bank_name": "Servio Bank",
                },
            )
            LegalEntityMembership.objects.get_or_create(
                user=user,
                legal_entity=legal_entity,
                defaults={"role": owner_role},
            )

            store, _ = SellerStore.objects.get_or_create(
                owner=user,
                defaults={
                    "name": row["store_name"],
                    "description": row["store_description"],
                    "legal_entity": legal_entity,
                },
            )
            store.name = row["store_name"]
            store.description = row["store_description"]
            store.legal_entity = legal_entity
            store.photo.save(f"seller_store_{idx}.png", ContentFile(TINY_PNG), save=False)
            store.save()

            sellers.append(user)

        products = list(Product.objects.order_by("id"))
        if products:
            iterator = cycle(sellers)
            for product in products:
                product.seller = next(iterator)
            Product.objects.bulk_update(products, ["seller"])

        self.stdout.write(self.style.SUCCESS(f"Sellers created/updated: {len(sellers)}"))
        self.stdout.write(self.style.SUCCESS(f"Products assigned to sellers: {len(products)}"))
        self.stdout.write(self.style.WARNING(f"Sample credentials: {seed_data[0]['username']} / {password}"))
