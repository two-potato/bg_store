from decimal import Decimal
import logging
from django.conf import settings
from django.core.cache import cache

from catalog.models import Product, Category
from .models import FavoriteProduct

log = logging.getLogger("shopfront")


def cart_badge(request):
    cart = request.session.get("cart", {}) or {}
    count = 0
    subtotal = Decimal("0.00")

    ids = []
    malformed = 0
    for raw_pid, payload in cart.items():
        try:
            pid = int(raw_pid)
            qty = max(0, int((payload or {}).get("qty", 0)))
        except Exception:
            malformed += 1
            continue
        count += qty
        if qty > 0:
            ids.append(pid)

    if ids:
        prices = dict(Product.objects.filter(id__in=ids).values_list("id", "price"))
        for raw_pid, payload in cart.items():
            try:
                pid = int(raw_pid)
                qty = max(0, int((payload or {}).get("qty", 0)))
            except Exception:
                malformed += 1
                continue
            price = prices.get(pid)
            if price is None or qty <= 0:
                continue
            subtotal += Decimal(str(price)) * Decimal(qty)

    if malformed:
        log.warning("cart_badge_malformed_items", extra={"malformed_items": malformed})

    return {
        "cart_badge_count": count,
        "cart_badge_subtotal": subtotal.quantize(Decimal("0.01")),
        "cart_product_ids": ids,
    }


def header_categories(request):
    cache_key = "shopfront:header_categories:v1"
    cats = cache.get(cache_key)
    if cats is None:
        cats = list(
            Category.objects.filter(parent__isnull=True)
            .order_by("name")
            .values("slug", "name")[:24]
        )
        cache.set(cache_key, cats, timeout=getattr(settings, "CACHE_TTL_HEADER_CATEGORIES", 900))
    return {"header_categories": cats}


def site_settings(request):
    canonical = request.build_absolute_uri(getattr(request, "path", "/"))
    default_description = "PotatoFarm - B2B маркетплейс товаров для бизнеса."
    default_image = request.build_absolute_uri("/media/user_photos/image017.jpg")
    return {
        "ga_measurement_id": getattr(settings, "GA_MEASUREMENT_ID", ""),
        "seo_title": "PotatoFarm",
        "seo_description": default_description,
        "seo_robots": "index,follow",
        "seo_canonical": canonical,
        "seo_og_type": "website",
        "seo_og_image": default_image,
    }


def favorites_state(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"favorite_product_ids": []}
    favorite_ids = list(
        FavoriteProduct.objects.filter(user=request.user).values_list("product_id", flat=True)[:2000]
    )
    return {"favorite_product_ids": favorite_ids}
