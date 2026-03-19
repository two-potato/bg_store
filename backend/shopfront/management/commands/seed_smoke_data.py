import hashlib

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from catalog.models import Brand, Category, Product
from shopfront.models import FavoriteProduct, PersistentCart


class Command(BaseCommand):
    help = "Seed a minimal deterministic catalog product for browser smoke and visual regression flows."

    def handle(self, *args, **options):
        user_model = get_user_model()
        brand, _ = Brand.objects.get_or_create(name="Smoke Brand")
        category, _ = Category.objects.get_or_create(name="Smoke Category")
        product, created = Product.objects.get_or_create(
            sku="99000001",
            defaults={
                "name": "Smoke Product",
                "brand": brand,
                "category": category,
                "price": 199,
                "stock_qty": 25,
                "pack_qty": 1,
                "unit": "шт",
                "min_order_qty": 1,
                "lead_time_days": 1,
                "is_new": True,
                "publication_status": Product.PublicationStatus.PUBLISHED,
                "description": "Deterministic product for browser smoke and visual checks.",
            },
        )
        if not created:
            changed = False
            desired = {
                "name": "Smoke Product",
                "brand": brand,
                "category": category,
                "price": 199,
                "stock_qty": 25,
                "pack_qty": 1,
                "unit": "шт",
                "min_order_qty": 1,
                "lead_time_days": 1,
                "is_new": True,
                "publication_status": Product.PublicationStatus.PUBLISHED,
                "description": "Deterministic product for browser smoke and visual checks.",
            }
            for field, value in desired.items():
                if getattr(product, field) != value:
                    setattr(product, field, value)
                    changed = True
            if changed:
                product.save()

        user, _ = user_model.objects.get_or_create(
            username="smoke-user",
            defaults={
                "email": "smoke@example.com",
                "is_active": True,
            },
        )
        changed = False
        if user.email != "smoke@example.com":
            user.email = "smoke@example.com"
            changed = True
        if not user.check_password("smoke-pass-2026"):
            user.set_password("smoke-pass-2026")
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if changed:
            user.save()

        FavoriteProduct.objects.filter(user=user, product=product).delete()
        PersistentCart.objects.update_or_create(user=user, defaults={"payload": {}})
        cache.delete_many(self._login_fail_cache_keys())

        self.stdout.write(self.style.SUCCESS(f"Seeded smoke product: {product.slug}"))
        self.stdout.write(self.style.SUCCESS(f"Seeded smoke user: {user.username}"))

    def _login_fail_cache_keys(self) -> list[str]:
        identifiers = ["smoke-user", "smoke@example.com"]
        keys = []
        for ident in identifiers:
            ident_hash = hashlib.sha256(ident.encode("utf-8")).hexdigest()[:24]
            keys.append(f"auth:login:fail:ident:{ident_hash}")
        keys.extend(
            [
                "auth:login:fail:ip:127.0.0.1",
                "auth:login:fail:ip:::1",
                "auth:login:fail:ip:localhost",
                "auth:login:fail:ip:unknown",
                "auth:login:fail:ip:172.17.0.1",
                "auth:login:fail:ip:172.18.0.1",
                "auth:login:fail:ip:172.19.0.1",
                "auth:login:fail:ip:172.20.0.1",
            ]
        )
        return keys
