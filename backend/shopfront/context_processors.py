from decimal import Decimal
import logging
from django.conf import settings
from django.core.cache import cache
from django.db.models import Prefetch
from django.urls import resolve, Resolver404

from catalog.models import Product, Category
from catalog.offer_service import active_offer_queryset, apply_offer_snapshot
from .models import FavoriteProduct

log = logging.getLogger("shopfront")


def cart_badge(request):
    cart = request.session.get("cart", {}) or {}
    count = 0
    subtotal = Decimal("0.00")
    qty_map = {}

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
        qty_map[pid] = qty
        if qty > 0:
            ids.append(pid)

    if ids:
        products = list(
            Product.objects.filter(id__in=ids).prefetch_related(
                Prefetch("seller_offers", queryset=active_offer_queryset())
            )
        )
        apply_offer_snapshot(products)
        prices = {product.id: product.display_price for product in products}
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
        "cart_qty_map": qty_map,
    }


def header_categories(request):
    cache_key = "shopfront:header_categories:v1"
    cats = cache.get(cache_key)
    if cats is None:
        cats = list(
            Category.objects.filter(parent__isnull=True)
            .exclude(name__startswith="HoReCa направление")
            .order_by("id")
            .values("slug", "name")[:14]
        )
        cache.set(cache_key, cats, timeout=getattr(settings, "CACHE_TTL_HEADER_CATEGORIES", 900))
    return {"header_categories": cats}


def site_settings(request):
    canonical = request.build_absolute_uri(getattr(request, "path", "/"))
    default_description = "Servio — маркетплейс товаров для HoReCa: единый каталог поставщиков, оптовые закупки и понятный b2b-сервис."
    default_image = request.build_absolute_uri("/media/user_photos/image017.jpg")
    page_type = "page"
    try:
        match = resolve(getattr(request, "path_info", "/"))
        page_type = (getattr(match, "url_name", "") or "page").replace("-", "_")
    except Resolver404:
        pass

    analytics_runtime_config = {
        "posthog_api_key": getattr(settings, "POSTHOG_API_KEY", ""),
        "posthog_host": getattr(settings, "POSTHOG_HOST", "https://app.posthog.com"),
        "clarity_project_id": getattr(settings, "CLARITY_PROJECT_ID", ""),
        "require_consent": bool(getattr(settings, "ANALYTICS_REQUIRE_CONSENT", True)),
        "page_type": page_type,
        "site_vertical": "horeca_marketplace",
        "currency": "RUB",
        "platform": "web",
    }
    analytics_identity_payload = {
        "is_authenticated": False,
        "user_state": "anonymous",
    }
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        profile = getattr(user, "profile", None)
        role = getattr(profile, "role", "buyer") or "buyer"
        analytics_identity_payload = {
            "is_authenticated": True,
            "user_state": "authenticated",
            "distinct_id": f"user:{user.id}",
            "clarity_custom_id": f"user:{user.id}",
            "clarity_friendly_name": getattr(user, "username", "") or f"user-{user.id}",
            "properties": {
                "user_id": user.id,
                "username": getattr(user, "username", "") or "",
                "role": role,
                "is_staff": bool(getattr(user, "is_staff", False)),
                "is_superuser": bool(getattr(user, "is_superuser", False)),
            },
        }

    return {
        "page_type": page_type,
        "ga_measurement_id": getattr(settings, "GA_MEASUREMENT_ID", ""),
        "posthog_api_key": analytics_runtime_config["posthog_api_key"],
        "posthog_host": analytics_runtime_config["posthog_host"],
        "clarity_project_id": analytics_runtime_config["clarity_project_id"],
        "analytics_require_consent": bool(getattr(settings, "ANALYTICS_REQUIRE_CONSENT", True)),
        "analytics_runtime_config": analytics_runtime_config,
        "analytics_identity_payload": analytics_identity_payload,
        "seo_title": "Servio",
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


def compare_state(request):
    compare_ids = []
    for raw_id in request.session.get("compare_products", []) or []:
        try:
            compare_ids.append(int(raw_id))
        except Exception:
            continue
    return {
        "compare_product_ids": compare_ids,
        "compare_count": len(compare_ids),
    }
