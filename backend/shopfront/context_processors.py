import os
import json
from hashlib import sha1

from decimal import Decimal
import logging
from django.conf import settings
from django.core.cache import cache
from django.db.models import Prefetch
from django.middleware.csrf import get_token
from django.templatetags.static import static
from django.urls import resolve, Resolver404

from catalog.models import Product, Category
from catalog.offer_service import active_offer_queryset, apply_offer_snapshot
from .request_state import favorite_product_ids_for_user, favorites_cache_key, session_cart_state

log = logging.getLogger("shopfront")


def _cart_payload_signature(cart: dict) -> str:
    """Internal helper for cart payload signature."""
    normalized = []
    for raw_pid, payload in sorted((cart or {}).items(), key=lambda item: str(item[0])):
        try:
            pid = int(raw_pid)
            qty = max(0, int((payload or {}).get("qty", 0)))
        except (TypeError, ValueError, AttributeError):
            continue
        normalized.append([pid, qty])
    return sha1(json.dumps(normalized, separators=(",", ":")).encode("utf-8")).hexdigest()


def invalidate_favorites_state(user_id: int) -> None:
    """Handle invalidate favorites state."""
    cache.delete(favorites_cache_key(user_id))


def _release() -> str:
    """Internal helper for release."""
    for key in ("SENTRY_RELEASE", "APP_RELEASE", "GIT_SHA", "RELEASE_SHA"):
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    return ""


def _public_sentry_dsn() -> str:
    """Internal helper for public sentry dsn."""
    explicit = (os.getenv("PUBLIC_SENTRY_DSN") or os.getenv("FRONTEND_SENTRY_DSN") or "").strip()
    dsn = explicit or (os.getenv("SENTRY_DSN") or "").strip()
    if not dsn:
        return ""
    return dsn.replace("host.docker.internal", "localhost")


def _sentry_browser_sdk_url() -> str:
    """Internal helper for sentry browser sdk url."""
    configured = (os.getenv("SENTRY_BROWSER_SDK_URL") or "").strip()
    if configured:
        return configured
    return "https://browser.sentry-cdn.com/8.33.1/bundle.min.js"


def cart_badge(request):
    """Handle cart badge."""
    cart = request.session.get("cart", {}) or {}
    count, qty_map, ids, malformed = session_cart_state(cart)

    subtotal = Decimal("0.00")
    price_map = {}
    if ids:
        cache_key = f"shopfront:cart_badge_prices:v1:{_cart_payload_signature(cart)}"
        cached = cache.get(cache_key)
        if cached is not None:
            try:
                price_map = {
                    int(pid): Decimal(str(price))
                    for pid, price in dict(cached).items()
                }
            except (TypeError, ValueError, ArithmeticError):
                price_map = {}
        if not price_map:
            products = list(
                Product.objects.filter(id__in=ids).prefetch_related(
                    Prefetch("seller_offers", queryset=active_offer_queryset())
                )
            )
            apply_offer_snapshot(products)
            price_map = {product.id: Decimal(str(product.display_price)) for product in products}
            cache.set(
                cache_key,
                {str(product_id): str(price) for product_id, price in price_map.items()},
                timeout=int(getattr(settings, "CACHE_TTL_CART_BADGE", 60)),
            )

    for pid, qty in qty_map.items():
        price = price_map.get(pid)
        if price is None or qty <= 0:
            continue
        subtotal += price * Decimal(qty)

    if malformed:
        log.warning("cart_badge_malformed_items", extra={"malformed_items": malformed})

    return {
        "cart_badge_count": count,
        "cart_badge_subtotal": subtotal.quantize(Decimal("0.01")),
    }


def header_categories(request):
    """Handle header categories."""
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
    """Handle site settings."""
    # Ensure storefront pages always issue a CSRF cookie for JS-driven POST flows.
    get_token(request)
    canonical = request.build_absolute_uri(getattr(request, "path", "/"))
    default_description = "Servio — маркетплейс товаров для HoReCa: единый каталог поставщиков, оптовые закупки и понятный b2b-сервис."
    default_image = request.build_absolute_uri(static("shopfront/big_logo.png"))
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
        "search_feedback_endpoint": "/analytics/search-feedback/",
        "recommendation_feedback_endpoint": "/analytics/recommendation-feedback/",
        "page_type": page_type,
        "site_vertical": "horeca_marketplace",
        "currency": "RUB",
        "platform": "web",
    }
    sentry_dsn = _public_sentry_dsn()
    monitoring_runtime_config = {
        "sentry_dsn": sentry_dsn,
        "sentry_environment": (os.getenv("SENTRY_ENVIRONMENT") or ("development" if settings.DEBUG else "production")).strip(),
        "sentry_release": _release(),
        "page_type": page_type,
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
        "gtm_container_id": getattr(settings, "GTM_CONTAINER_ID", ""),
        "posthog_api_key": analytics_runtime_config["posthog_api_key"],
        "posthog_host": analytics_runtime_config["posthog_host"],
        "clarity_project_id": analytics_runtime_config["clarity_project_id"],
        "analytics_require_consent": bool(getattr(settings, "ANALYTICS_REQUIRE_CONSENT", True)),
        "analytics_runtime_config": analytics_runtime_config,
        "monitoring_runtime_config": monitoring_runtime_config,
        "sentry_browser_sdk_url": _sentry_browser_sdk_url(),
        "analytics_identity_payload": analytics_identity_payload,
        "seo_title": "Servio",
        "seo_description": default_description,
        "seo_robots": "index,follow",
        "seo_canonical": canonical,
        "seo_og_type": "website",
        "seo_og_image": default_image,
    }


def favorites_state(request):
    """Handle favorites state."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    favorite_product_ids_for_user(request.user, limit=2000)
    return {}


def compare_state(request):
    """Handle compare state."""
    compare_ids = []
    for raw_id in request.session.get("compare_products", []) or []:
        try:
            compare_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    compare_products = []
    if compare_ids:
        order_map = {pid: idx for idx, pid in enumerate(compare_ids)}
        compare_products = sorted(
            Product.objects.filter(id__in=compare_ids)
            .select_related("brand")
            .only("id", "name", "slug", "brand__name"),
            key=lambda product: order_map.get(product.id, 999),
        )
    return {
        "compare_product_ids": compare_ids,
        "compare_count": len(compare_ids),
        "compare_items": compare_products[:4],
    }
