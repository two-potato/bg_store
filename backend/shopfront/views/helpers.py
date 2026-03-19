from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from catalog.models import (
    Product,
    Category,
    Brand,
    Tag,
    ProductImage,
    ProductReview,
    ProductReviewComment,
    ProductReviewVote,
    Collection,
    SellerOffer,
    normalize_public_media_url,
)
from catalog.offer_service import active_offer_queryset, apply_offer_snapshot, resolve_product_offer
from django.core.paginator import Paginator, EmptyPage
from django.views import View
from django.views.generic import TemplateView
from django_fsm import TransitionNotAllowed
from django.utils.decorators import method_decorator
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.csrf import ensure_csrf_cookie
from django.middleware.csrf import get_token
from django.core.cache import cache
from django.contrib import messages
from django.db.models import Avg, Count, Case, When, IntegerField, Value, FloatField, Prefetch
from django.db.models import Q
from django.db import transaction
from django.db.models.functions import Coalesce
from orders.models import Order, OrderItem, FakeAcquiringPayment, OrderApprovalLog
from orders.payment_providers import get_payment_provider
from orders.services import plan_seller_splits
from commerce.models import LegalEntityMembership, DeliveryAddress, SellerStore, StoreReview
from commerce.company_service import resolve_order_approval_requirement
from ..forms import ContactFeedbackForm
from ..models import (
    FavoriteProduct,
    SavedSearch,
    PersistentCart,
    CategorySubscription,
    BrandSubscription,
    SavedList,
    SavedListItem,
)
from ..tasks import notify_contact_feedback
from ..cart_store import persist_cart_for_user
from ..cart_checkout_service import (
    cart_badge_context as _cart_badge_context,
    cart_summary as _cart_summary,
    checkout_addresses_queryset,
    checkout_cart_tracking_payload,
    checkout_company_snapshots,
    checkout_identity_defaults,
    session_cart as _cart,
)
from ..checkout_flow_service import (
    build_checkout_context as _build_checkout_context,
    ensure_checkout_idempotency_key,
    fake_payment_template_context,
)
from ..catalog_selectors import (
    cached_catalog_default_page_ids as _cached_catalog_default_page_ids,
    cached_catalog_default_total_count as _cached_catalog_default_total_count,
    cached_home_category_ids as _cached_home_category_ids,
    cached_home_product_ids as _cached_home_product_ids,
    catalog_price_stats as _catalog_price_stats,
    category_breadcrumbs as _category_breadcrumbs,
    category_descendant_ids as _category_descendant_ids,
    category_option_rows as _category_option_rows,
    category_slug_path as _category_slug_path,
    facet_option_counts as _facet_option_counts,
    ordered_products_with_related as _ordered_products_with_related,
    seller_facet_counts as _seller_facet_counts,
    with_rating as _with_rating,
)
from ..search_service import get_search_provider, DatabaseSearchProvider, suggest_query_corrections
from ..recommendations import (
    record_recent_view,
    recently_viewed_ids_for_user,
    frequently_bought_together_ids,
    seller_cross_sell_ids,
    personalized_home_sections,
    featured_collection_ids,
    brand_highlight_ids,
)
from ..recommendation_events import recommendation_impression_payload
from ..recommendation_service import product_section_context
from ..review_service import (
    apply_review_vote,
    build_reviews_context,
    create_product_question,
    create_review_comment,
    delete_product_review,
    delete_review_comment,
    render_reviews_partial,
    update_review_comment,
    upsert_product_review,
)
from ..live_search_service import live_search_context
from ..cart_mutation_service import (
    add_to_cart_session,
    clear_cart_session,
    remove_from_cart_session,
    update_cart_session,
)
from promotions.services import create_redemption, resolve_checkout_discount
import logging
import json
import hmac
from uuid import uuid4
from django.utils import timezone
from core.logging_utils import log_calls
from decimal import Decimal
from decimal import InvalidOperation
from .. import search as sf_search
from urllib.parse import urlencode
from django.urls import reverse
from xml.sax.saxutils import escape
from users.models import UserProfile
log = logging.getLogger("shopfront")
COMPARE_SESSION_KEY = "compare_products"
COMPARE_LIMIT = 4


@log_calls(log)
def robots_txt(request):
    host = request.get_host().split(":")[0]
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /api/",
        "Disallow: /api/docs/",
        "Disallow: /api/schema/",
        "Disallow: /account/",
        "Disallow: /checkout/",
        "Disallow: /payments/fake/",
        "Disallow: /metrics",
        "Disallow: /metrics/",
        f"Sitemap: https://{host}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


@log_calls(log)
def sitemap_xml(request):
    host = request.get_host().split(":")[0]
    base = f"https://{host}"
    static_entries = [
        (reverse("home"), timezone.now()),
        (reverse("catalog"), timezone.now()),
        (reverse("products"), timezone.now()),
        (reverse("categories"), timezone.now()),
        (reverse("vendors"), timezone.now()),
        (reverse("search"), timezone.now()),
        (reverse("buyers"), timezone.now()),
        (reverse("suppliers"), timezone.now()),
        (reverse("brands"), timezone.now()),
        (reverse("promotions"), timezone.now()),
        (reverse("blog"), timezone.now()),
        (reverse("about"), timezone.now()),
        (reverse("delivery"), timezone.now()),
        (reverse("payment"), timezone.now()),
        (reverse("returns"), timezone.now()),
        (reverse("faq"), timezone.now()),
        (reverse("contacts"), timezone.now()),
    ]
    urls = [(base + path, updated_at) for path, updated_at in static_entries]
    urls.extend(
        [
            (base + reverse("product", kwargs={"slug": slug}), updated_at)
            for slug, updated_at in Product.objects.exclude(slug="").values_list("slug", "updated_at")[:50000]
        ]
    )
    categories = list(
        Category.objects.select_related("parent")
        .exclude(slug="")
        .only("slug", "parent_id", "updated_at")
    )
    urls.extend(
        [
            (base + reverse("category_detail", kwargs={"category_slug": _category_path(category)}), category.updated_at)
            for category in categories
            if _category_path(category)
        ]
    )
    urls.extend(
        [
            (base + reverse("vendor_detail", kwargs={"vendor_slug": slug}), updated_at)
            for slug, updated_at in SellerStore.objects.exclude(slug="").values_list("slug", "updated_at")[:50000]
        ]
    )
    profile_lastmod = timezone.now()
    urls.extend(
        [
            (base + reverse("vendor_detail", kwargs={"vendor_slug": slug}), profile_lastmod)
            for slug in UserProfile.objects.exclude(slug="").exclude(user__seller_store__isnull=False).values_list("slug", flat=True)[:50000]
        ]
    )
    urls.extend(
        [
            (base + reverse("brand_detail", kwargs={"brand_slug": slug}), updated_at)
            for slug, updated_at in Brand.objects.exclude(slug="").values_list("slug", "updated_at")[:50000]
        ]
    )
    urls.extend(
        [
            (base + reverse("collection_detail", kwargs={"collection_slug": slug}), updated_at)
            for slug, updated_at in Collection.objects.filter(is_active=True).exclude(slug="").values_list("slug", "updated_at")[:50000]
        ]
    )

    body = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>", "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"]
    for loc, lastmod in urls:
        body.append(
            f"  <url><loc>{escape(loc)}</loc><lastmod>{lastmod.date().isoformat()}</lastmod></url>"
        )
    body.append("</urlset>")
    return HttpResponse("\n".join(body), content_type="application/xml; charset=utf-8")


def _absolute_url(request, path: str) -> str:
    return request.build_absolute_uri(normalize_public_media_url(path))


def _truncate_text(value: str, limit: int = 160) -> str:
    text = (value or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _default_og_image(request) -> str:
    return _absolute_url(request, "/static/shopfront/big_logo.png")


def _product_primary_image(product: Product):
    prefetched = getattr(product, "prefetched_images", None)
    if prefetched is not None:
        return prefetched[0] if prefetched else None
    images = list(product.images.all())
    return images[0] if images else None


def _seo_context(
    request,
    *,
    title: str,
    description: str,
    canonical: str | None = None,
    robots: str = "index,follow",
    og_type: str = "website",
    og_image: str | None = None,
    json_ld: dict | list | None = None,
):
    canonical_url = canonical or _absolute_url(request, request.path)
    context = {
        "seo_title": title,
        "seo_description": _truncate_text(description, 170),
        "seo_canonical": canonical_url,
        "seo_robots": robots,
        "seo_og_type": og_type,
        "seo_og_image": og_image or _default_og_image(request),
    }
    if json_ld is not None:
        context["seo_json_ld"] = json.dumps(json_ld, ensure_ascii=False)
    return context


def _website_json_ld(request):
    base = _absolute_url(request, "/")
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "Servio",
        "url": base,
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{base}search/?q={{search_term_string}}",
            "query-input": "required name=search_term_string",
        },
    }


def _organization_json_ld(request):
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Servio",
        "url": _absolute_url(request, "/"),
        "logo": _absolute_url(request, "/static/shopfront/favicon.svg"),
        "contactPoint": [
            {
                "@type": "ContactPoint",
                "contactType": "customer support",
                "email": "hello@servio.market",
                "telephone": "+7-495-120-42-20",
                "availableLanguage": ["ru"],
            }
        ],
    }


def _product_json_ld(request, product: Product, seller_store: SellerStore | None = None):
    images = []
    for img in getattr(product, "prefetched_images", None) or product.images.all():
        try:
            images.append(_absolute_url(request, img.url))
        except Exception:
            continue
    if not images:
        images.append(_default_og_image(request))
    price = getattr(product, "display_price", None) or product.price
    stock_qty = getattr(product, "display_stock_qty", None)
    if stock_qty is None:
        stock_qty = product.stock_qty
    availability = "https://schema.org/InStock" if (stock_qty or 0) > 0 else "https://schema.org/OutOfStock"
    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "sku": product.sku or "",
        "image": images,
        "description": _truncate_text(product.description or f"{product.name} в каталоге Servio для профессиональных закупок HoReCa.", 300),
        "brand": {"@type": "Brand", "name": getattr(product.brand, "name", "") or ""},
        "offers": {
            "@type": "Offer",
            "priceCurrency": "RUB",
            "price": str(price),
            "availability": availability,
            "url": _absolute_url(request, reverse("product", kwargs={"slug": product.slug})),
        },
    }
    if seller_store:
        data["seller"] = {"@type": "Organization", "name": seller_store.name}
    return data


def _cache_get(key, default=None):
    try:
        return cache.get(key, default)
    except Exception:
        log.warning("cache_get_failed", extra={"cache_key": key}, exc_info=True)
        return default


def _cache_set(key, value, timeout):
    try:
        cache.set(key, value, timeout=timeout)
    except Exception:
        log.warning("cache_set_failed", extra={"cache_key": key}, exc_info=True)


def _parse_decimal_filter(raw_value: str | None) -> Decimal | None:
    value = (raw_value or "").strip().replace(",", ".")
    if not value:
        return None
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed.quantize(Decimal("0.01"))


def _new_idempotency_key() -> str:
    return uuid4().hex


def _new_guest_access_token() -> str:
    return uuid4().hex


def _demo_payments_enabled() -> bool:
    return bool(getattr(settings, "ENABLE_DEMO_PAYMENTS", settings.DEBUG))


def _allowed_payment_methods() -> tuple[str, ...]:
    methods = [Order.PaymentMethod.CASH, Order.PaymentMethod.INVOICE]
    if _demo_payments_enabled():
        methods.extend([Order.PaymentMethod.MIR_CARD, Order.PaymentMethod.ONLINE_CARD])
    return tuple(methods)


def _visible_brand_filter_options(brands, facet_brand_options, selected_brand):
    limit = max(8, int(getattr(settings, "CATALOG_FILTER_BRAND_LIMIT", 24)))
    selected_ids = {option["id"] for option in facet_brand_options}
    if selected_brand is not None:
        selected_ids.add(selected_brand.id)
    selected = [brand for brand in brands if brand.id in selected_ids]
    if len(selected) >= limit:
        return selected[:limit]
    selected_set = {brand.id for brand in selected}
    for brand in brands:
        if brand.id in selected_set:
            continue
        selected.append(brand)
        if len(selected) >= limit:
            break
    return selected


def _visible_tag_filter_options(tags, selected_tag):
    limit = max(8, int(getattr(settings, "CATALOG_FILTER_TAG_LIMIT", 24)))
    if not selected_tag:
        return tags[:limit]
    selected = [tag for tag in tags if str(tag.id) == str(selected_tag) or tag.slug == str(selected_tag)]
    selected_ids = {tag.id for tag in selected}
    for tag in tags:
        if tag.id in selected_ids:
            continue
        selected.append(tag)
        if len(selected) >= limit:
            break
    return selected[:limit]


def _catalog_filter_suggestion_limit() -> int:
    return max(5, min(20, int(getattr(settings, "CATALOG_FILTER_SUGGESTION_LIMIT", 8))))


def _catalog_filter_cache_timeout() -> int:
    return int(getattr(settings, "CACHE_TTL_CATALOG_FILTERS", 900))


def _cached_catalog_brands():
    latest_id = Brand.objects.order_by("-id").values_list("id", flat=True).first() or 0
    brands = _cache_get(f"shopfront:catalog:brands:v2:{latest_id}")
    if brands is None:
        brands = list(Brand.objects.only("id", "name").order_by("name"))
        _cache_set(f"shopfront:catalog:brands:v2:{latest_id}", brands, timeout=_catalog_filter_cache_timeout())
    return brands


def _cached_catalog_categories():
    latest_id = Category.objects.order_by("-id").values_list("id", flat=True).first() or 0
    categories = _cache_get(f"shopfront:catalog:categories:v2:{latest_id}")
    if categories is None:
        categories = list(
            Category.objects.select_related("parent")
            .exclude(name__startswith="HoReCa направление")
            .only("id", "name", "slug", "parent_id")
            .order_by("parent_id", "name", "id")
        )
        _cache_set(
            f"shopfront:catalog:categories:v2:{latest_id}",
            categories,
            timeout=_catalog_filter_cache_timeout(),
        )
    return categories


def _cached_catalog_tags():
    latest_id = Tag.objects.order_by("-id").values_list("id", flat=True).first() or 0
    tags = _cache_get(f"shopfront:catalog:tags:v3:{latest_id}")
    if tags is None:
        tags = list(Tag.objects.only("id", "name", "slug").order_by("name"))
        _cache_set(f"shopfront:catalog:tags:v3:{latest_id}", tags, timeout=_catalog_filter_cache_timeout())
    return tags


def _category_breadcrumb_label_map(categories) -> dict[int, str]:
    by_id = {category.id: category for category in categories}
    labels: dict[int, str] = {}
    for category in categories:
        parts = []
        cursor = category
        safety = 0
        while cursor is not None and safety < 12:
            parts.append(cursor.name)
            cursor = by_id.get(cursor.parent_id)
            safety += 1
        labels[category.id] = " / ".join(reversed(parts))
    return labels


def _category_path(category: Category | None) -> str:
    return _category_slug_path(category)


def _category_url(category: Category | None) -> str:
    if category is None:
        return reverse("categories")
    return reverse("category_detail", kwargs={"category_slug": _category_path(category)})


def _product_url(product: Product) -> str:
    return reverse("product", kwargs={"slug": product.slug})


def _seller_store_for_user(user):
    if user is None:
        return None
    return SellerStore.objects.filter(owner=user).first()


def _vendor_slug_for_user(user) -> str:
    store = _seller_store_for_user(user)
    if store is not None and getattr(store, "slug", ""):
        return store.slug
    profile = getattr(user, "profile", None)
    if profile is not None and getattr(profile, "slug", ""):
        return profile.slug
    return ""


def _vendor_url(store: SellerStore | None = None, user=None) -> str:
    if store is not None and getattr(store, "slug", ""):
        return reverse("vendor_detail", kwargs={"vendor_slug": store.slug})
    if user is not None:
        slug = _vendor_slug_for_user(user)
        if slug:
            return reverse("vendor_detail", kwargs={"vendor_slug": slug})
    return reverse("vendors")


def _selected_tag_object(selected_tag, tags):
    if not selected_tag:
        return None
    selected_raw = str(selected_tag)
    for tag in tags:
        if str(tag.id) == selected_raw or tag.slug == selected_raw:
            return tag
    if selected_raw.isdigit():
        return Tag.objects.only("id", "name", "slug").filter(id=int(selected_raw)).first()
    return Tag.objects.only("id", "name", "slug").filter(slug=selected_raw).first()


def _guest_order_session_map(request) -> dict[str, str]:
    raw = request.session.get("guest_order_tokens", {}) or {}
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items() if key and value}
    return {}


def _remember_guest_order(request, order: Order) -> None:
    token = order.guest_access_token or ""
    if not token:
        return
    payload = _guest_order_session_map(request)
    payload[str(order.id)] = token
    request.session["guest_order_tokens"] = payload
    request.session.modified = True


def _has_guest_order_access(request, order: Order, token: str | None = None) -> bool:
    if request.user.is_authenticated and order.placed_by_id and order.placed_by_id == request.user.id:
        return True
    expected = (order.guest_access_token or "").strip()
    provided = (token or "").strip()
    if expected and provided and hmac.compare_digest(expected, provided):
        return True
    session_token = _guest_order_session_map(request).get(str(order.id), "")
    return bool(expected and session_token and hmac.compare_digest(session_token, expected))


def _order_detail_url(order: Order) -> str:
    if order.is_guest and order.guest_access_token:
        return reverse("guest_order_detail", kwargs={"order_id": order.id, "token": order.guest_access_token})
    return f"/account/orders/{order.id}/"


def _fake_payment_page_url(order: Order) -> str:
    if order.is_guest and order.guest_access_token:
        return reverse("guest_fake_payment_page", kwargs={"order_id": order.id, "token": order.guest_access_token})
    return reverse("fake_payment_page", kwargs={"order_id": order.id})


def _fake_payment_event_url(order: Order) -> str:
    if order.is_guest and order.guest_access_token:
        return reverse("guest_fake_payment_event", kwargs={"order_id": order.id, "token": order.guest_access_token})
    return reverse("fake_payment_event", kwargs={"order_id": order.id})


def _online_payment_page_url(order: Order) -> str:
    if order.is_guest and order.guest_access_token:
        return reverse("guest_online_payment_page", kwargs={"order_id": order.id, "token": order.guest_access_token})
    return reverse("online_payment_page", kwargs={"order_id": order.id})


def _online_payment_event_url(order: Order) -> str:
    if order.is_guest and order.guest_access_token:
        return reverse("guest_online_payment_event", kwargs={"order_id": order.id, "token": order.guest_access_token})
    return reverse("online_payment_event", kwargs={"order_id": order.id})


def _tracking_item_from_product(product: Product, quantity: int = 1) -> dict:
    category_name = getattr(product.category, "name", "") or ""
    seller = getattr(product, "seller", None)
    seller_store = _seller_store_for_user(seller)
    offer = getattr(product, "active_offer", None) or resolve_product_offer(product)
    seller_store = getattr(offer, "seller_store", None) or seller_store
    price = getattr(product, "display_price", None) or getattr(offer, "price", None) or product.price
    return {
        "item_id": product.sku or str(product.id),
        "item_name": product.name,
        "item_brand": getattr(product.brand, "name", "") or "",
        "item_category": category_name,
        "item_variant": getattr(getattr(product, "series", None), "name", "") or "",
        "item_seller": getattr(seller_store, "name", "") or "",
        "price": float(Decimal(str(price)).quantize(Decimal("0.01"))),
        "quantity": max(1, int(quantity or 1)),
    }


def _order_tracking_payload(order: Order) -> dict:
    items = [_tracking_item_from_product(item.product, quantity=item.qty) for item in order.items.select_related("product", "product__brand", "product__category", "product__series", "product__seller", "product__seller__seller_store").all()]
    return {
        "event": "purchase",
        "seller_count": order.seller_splits.count(),
        "coupon": order.coupon_code or "",
        "source_channel": order.source_channel,
        "ecommerce": {
            "transaction_id": str(order.id),
            "currency": "RUB",
            "value": float(order.total),
            "discount": float(order.discount_amount),
            "items": items,
        },
    }


def _checkout_items_payload(items, total: Decimal, seller_count: int) -> dict:
    return {
        "seller_count": seller_count,
        "ecommerce": {
            "currency": "RUB",
            "value": float(total),
            "items": [_tracking_item_from_product(it["p"], quantity=it["qty"]) for it in items],
        },
    }


def _recommendation_impression_payload(source: str, products) -> str:
    return recommendation_impression_payload(source, products)


def _product_recommendation_section(product: Product, section: str) -> dict:
    try:
        return product_section_context(product, section)
    except ValueError as exc:
        raise Http404("Unknown recommendation section") from exc


def _checkout_step_tracking_payload(step_name: str, *, items, total: Decimal, seller_count: int) -> dict:
    return {
        "event": "checkout_step_view",
        "checkout_step": step_name,
        **_checkout_items_payload(items, total, seller_count),
    }


def _checkout_error_tracking_payload(reason: str, *, customer_type: str = "", payment_method: str = "", items=None, total: Decimal = Decimal("0.00"), seller_count: int = 0) -> dict:
    payload = {
        "event": "checkout_error",
        "checkout_step": "details",
        "error_message": reason,
        "customer_type": customer_type or "",
        "payment_method": payment_method or "",
    }
    if items:
        payload.update(_checkout_items_payload(items, total, seller_count))
    return payload


def _payment_tracking_payload(event_name: str, order: Order, payment: FakeAcquiringPayment | None = None, *, payment_event: str = "") -> dict:
    payload = {
        "event": event_name,
        "payment_method": order.payment_method,
        "checkout_step": "payment",
        "order_id": str(order.id),
        "customer_type": order.customer_type,
        "seller_count": order.seller_splits.count(),
        "source_channel": order.source_channel,
        "ecommerce": {
            "transaction_id": str(order.id),
            "currency": "RUB",
            "value": float(order.total),
            "items": [
                _tracking_item_from_product(item.product, quantity=item.qty)
                for item in order.items.select_related("product", "product__brand", "product__category", "product__series", "product__seller", "product__seller__seller_store").all()
            ],
        },
    }
    if payment is not None:
        payload["payment_status"] = payment.status
        payload["provider_payment_id"] = payment.provider_payment_id
    if payment_event:
        payload["payment_event"] = payment_event
    return payload


def _record_recently_viewed(request, product: Product, limit: int = 12) -> None:
    key = "recently_viewed_products"
    existing = [int(pid) for pid in request.session.get(key, []) if str(pid).isdigit()]
    existing = [pid for pid in existing if pid != product.id]
    request.session[key] = [product.id] + existing[: max(0, limit - 1)]
    request.session.modified = True
    record_recent_view(request.user, product, limit=max(limit, 24))


def _recently_viewed_products(request, exclude_product_id: int | None = None, limit: int = 8):
    ids = [int(pid) for pid in request.session.get("recently_viewed_products", []) if str(pid).isdigit()]
    if request.user.is_authenticated:
        persistent_ids = recently_viewed_ids_for_user(request.user, limit=max(limit * 2, 12))
        ids = ids + [pid for pid in persistent_ids if pid not in ids]
    if exclude_product_id is not None:
        ids = [pid for pid in ids if pid != exclude_product_id]
    return _ordered_products_with_related(ids[:limit], include_rating=True)


def _cached_id_list(cache_key: str, ttl: int, builder) -> list[int]:
    ids = _cache_get(cache_key)
    if ids is None:
        ids = list(builder())
        _cache_set(cache_key, ids, timeout=ttl)
    return [int(pid) for pid in ids if str(pid).isdigit()]


def _seller_rating_summary(seller_id: int | None) -> dict:
    if not seller_id:
        return {"rating_avg": 0, "rating_count": 0}
    cache_key = f"shopfront:seller_rating:v1:{seller_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    agg = ProductReview.objects.filter(product__seller_id=seller_id).aggregate(
        rating_avg=Coalesce(Avg("rating"), Value(0.0), output_field=FloatField()),
        rating_count=Count("id"),
    )
    payload = {
        "rating_avg": agg["rating_avg"] or 0,
        "rating_count": agg["rating_count"] or 0,
    }
    _cache_set(cache_key, payload, timeout=getattr(settings, "CACHE_TTL_PDP_SUMMARY", 300))
    return payload


def _store_rating_summary(store: SellerStore | None) -> dict:
    if store is None:
        return {"rating_avg": 0, "rating_count": 0}
    cache_key = f"shopfront:store_rating:v1:{store.id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    agg = StoreReview.objects.filter(store=store).aggregate(
        rating_avg=Coalesce(Avg("rating"), Value(0.0), output_field=FloatField()),
        rating_count=Count("id"),
    )
    payload = {
        "rating_avg": agg["rating_avg"] or 0,
        "rating_count": agg["rating_count"] or 0,
    }
    _cache_set(cache_key, payload, timeout=getattr(settings, "CACHE_TTL_PDP_SUMMARY", 300))
    return payload


def _store_reviews_context(store: SellerStore, user):
    reviews_qs = store.reviews.select_related("user", "user__profile")
    agg = reviews_qs.aggregate(avg=Avg("rating"), count=Count("id"))
    user_review = reviews_qs.filter(user=user).first() if getattr(user, "is_authenticated", False) else None
    return {
        "store": store,
        "store_reviews": reviews_qs[:20],
        "store_rating_avg": agg["avg"] or 0,
        "store_rating_count": agg["count"] or 0,
        "store_user_review": user_review,
    }


def _compare_ids(request) -> list[int]:
    ids: list[int] = []
    for raw_id in request.session.get(COMPARE_SESSION_KEY, []) or []:
        try:
            product_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if product_id not in ids:
            ids.append(product_id)
    return ids[:COMPARE_LIMIT]


def _set_compare_ids(request, product_ids: list[int]) -> list[int]:
    normalized: list[int] = []
    for product_id in product_ids:
        try:
            candidate = int(product_id)
        except (TypeError, ValueError):
            continue
        if candidate not in normalized:
            normalized.append(candidate)
    request.session[COMPARE_SESSION_KEY] = normalized[:COMPARE_LIMIT]
    request.session.modified = True
    return request.session[COMPARE_SESSION_KEY]


def _compare_fields(products: list[Product]) -> list[dict]:
    attribute_keys: list[str] = []
    seen_keys: set[str] = set()
    for product in products:
        for key in (product.attributes or {}).keys():
            if key in seen_keys:
                continue
            seen_keys.add(key)
            attribute_keys.append(key)

    rows = [
        {"label": "Цена", "values": [f"{product.display_price} ₽" for product in products]},
        {"label": "Бренд", "values": [getattr(product.brand, "name", "—") or "—" for product in products]},
        {"label": "Серия", "values": [getattr(product.series, "name", "—") or "—" for product in products]},
        {"label": "Категория", "values": [getattr(product.category, "name", "—") or "—" for product in products]},
        {"label": "Магазин", "values": [getattr(_seller_store_for_user(getattr(product, "seller", None)), "name", "—") or "—" for product in products]},
        {
            "label": "Рейтинг",
            "values": [
                f"{product.rating_avg:.1f} / 5 ({product.rating_count})" if getattr(product, "rating_count", 0) else "Нет оценок"
                for product in products
            ],
        },
        {"label": "Наличие", "values": [str(product.display_stock_qty) if product.display_stock_qty > 0 else "Нет в наличии" for product in products]},
        {"label": "MOQ", "values": [f"от {product.display_min_order_qty} {product.unit}" for product in products]},
        {
            "label": "Срок поставки",
            "values": [f"{product.display_lead_time_days} дн." if product.display_lead_time_days else "1-2 дня" for product in products],
        },
        {"label": "Упаковка", "values": [f"{product.pack_qty} {product.unit}" for product in products]},
        {"label": "Материал", "values": [product.material or "—" for product in products]},
        {"label": "Объём", "values": [f"{product.volume_ml} мл" if product.volume_ml else "—" for product in products]},
    ]
    for key in attribute_keys:
        rows.append(
            {
                "label": key,
                "values": [str((product.attributes or {}).get(key, "—") or "—") for product in products],
            }
        )
    return rows


def _cart_add_product(request, product_id: int, qty: int = 1) -> int:
    cart = _cart(request)
    key = str(product_id)
    current = cart.get(key, {})
    current_qty = max(0, int(current.get("qty", 0) or 0))
    cart[key] = {"qty": current_qty + max(1, int(qty or 1))}
    request.session["cart"] = cart
    request.session.modified = True
    persist_cart_for_user(request.user, request.session.get("cart", {}))
    return cart[key]["qty"]


def _saved_list_queryset(user):
    return SavedList.objects.filter(user=user).prefetch_related("items__product__images").order_by("-updated_at", "-id")


def _saved_list_add_products(saved_list: SavedList, product_ids: list[int], quantities: dict[int, int] | None = None) -> int:
    quantities = quantities or {}
    added = 0
    existing = {
        item.product_id: item for item in SavedListItem.objects.filter(saved_list=saved_list, product_id__in=product_ids)
    }
    for ordering, product_id in enumerate(product_ids, start=1):
        qty = max(1, int(quantities.get(product_id, 1) or 1))
        item = existing.get(product_id)
        if item:
            item.quantity = qty
            item.ordering = min(item.ordering or ordering, ordering)
            item.save(update_fields=["quantity", "ordering", "updated_at"])
            continue
        SavedListItem.objects.create(
            saved_list=saved_list,
            product_id=product_id,
            quantity=qty,
            ordering=ordering,
        )
        added += 1
    return added


def _payment_event_label(event_code: str) -> str:
    return dict(FakeAcquiringPayment.Event.choices).get(event_code, event_code)


def _append_payment_history(payment: FakeAcquiringPayment, event_code: str, status_code: str, note: str = ""):
    history = list(payment.history or [])
    history.append(
        {
            "at": timezone.now().strftime("%d.%m.%Y %H:%M:%S"),
            "event": event_code,
            "event_label": _payment_event_label(event_code),
            "status": status_code,
            "status_label": dict(FakeAcquiringPayment.Status.choices).get(status_code, status_code),
            "note": note,
        }
    )
    payment.history = history[-50:]
    payment.last_event = event_code
    payment.status = status_code


def _apply_fake_payment_event(order: Order, payment: FakeAcquiringPayment, event_code: str):
    status_map = {
        FakeAcquiringPayment.Event.START: FakeAcquiringPayment.Status.PROCESSING,
        FakeAcquiringPayment.Event.REQUIRE_3DS: FakeAcquiringPayment.Status.REQUIRES_3DS,
        FakeAcquiringPayment.Event.PASS_3DS: FakeAcquiringPayment.Status.PAID,
        FakeAcquiringPayment.Event.SUCCESS: FakeAcquiringPayment.Status.PAID,
        FakeAcquiringPayment.Event.FAIL: FakeAcquiringPayment.Status.FAILED,
        FakeAcquiringPayment.Event.CANCEL: FakeAcquiringPayment.Status.CANCELED,
        FakeAcquiringPayment.Event.REFUND: FakeAcquiringPayment.Status.REFUNDED,
    }
    next_status = status_map.get(event_code)
    if not next_status:
        return
    _append_payment_history(payment, event_code, next_status)
    payment.save(update_fields=["history", "last_event", "status", "updated_at"])

    if next_status == FakeAcquiringPayment.Status.PAID:
        if order.status in {Order.Status.NEW, Order.Status.CHANGED}:
            try:
                order.approve()
            except TransitionNotAllowed:
                order.status = Order.Status.CONFIRMED
            order.save(update_fields=["status"])
        if order.status == Order.Status.CONFIRMED:
            try:
                order.pay()
            except TransitionNotAllowed:
                order.status = Order.Status.PAID
            order.save(update_fields=["status"])
    elif next_status in {FakeAcquiringPayment.Status.FAILED, FakeAcquiringPayment.Status.CANCELED}:
        if order.status not in {Order.Status.CANCELED, Order.Status.DELIVERED}:
            try:
                order.cancel()
            except TransitionNotAllowed:
                order.status = Order.Status.CANCELED
            order.save(update_fields=["status"])
    elif next_status == FakeAcquiringPayment.Status.REFUNDED:
        if order.status not in {Order.Status.CANCELED, Order.Status.DELIVERED}:
            try:
                order.mark_changed()
            except TransitionNotAllowed:
                order.status = Order.Status.CHANGED
            order.save(update_fields=["status"])

def _checkout_context(req, form_data=None, checkout_error=None):
    cart_ctx = _cart_summary(req)
    memberships = LegalEntityMembership.objects.none()
    addresses = DeliveryAddress.objects.none()
    individual_default_name = ""
    individual_default_email = ""
    if req.user.is_authenticated:
        memberships = LegalEntityMembership.objects.select_related("legal_entity").filter(user=req.user)
        addresses = checkout_addresses_queryset(req)
        individual_default_name, individual_default_email = checkout_identity_defaults(req)
    company_snapshots = checkout_company_snapshots(req, memberships)
    checkout_idem_key = ensure_checkout_idempotency_key(req, _new_idempotency_key)
    return _build_checkout_context(
        request=req,
        cart_ctx=cart_ctx,
        memberships=memberships,
        addresses=addresses,
        form_data=form_data,
        checkout_error=checkout_error or "",
        checkout_idem_key=checkout_idem_key,
        individual_default_name=individual_default_name,
        individual_default_email=individual_default_email,
        company_snapshots=company_snapshots,
        checkout_step_tracking_payload=_checkout_step_tracking_payload(
            "details",
            items=cart_ctx["items"],
            total=cart_ctx["total"],
            seller_count=cart_ctx["seller_count"],
        ),
        checkout_error_tracking_payload=_checkout_error_tracking_payload(
            checkout_error or "",
            customer_type=str((form_data or {}).get("customer_type") or ""),
            payment_method=str((form_data or {}).get("payment_method") or ""),
            items=cart_ctx["items"],
            total=cart_ctx["total"],
            seller_count=cart_ctx["seller_count"],
        ),
        checkout_cart_tracking_payload=checkout_cart_tracking_payload(cart_ctx, _tracking_item_from_product),
        demo_payments_enabled=_demo_payments_enabled(),
    )

def _render_cart_fragment(request, items, subtotal, discount_percent, discount_amount, total, status=200):
    target = (request.headers.get("HX-Target") or "").strip()
    template = "shopfront/partials/cart_content.html" if target == "cart-root" else "shopfront/partials/cart_panel.html"
    return render(
        request,
        template,
        {
            "items": items,
            "subtotal": subtotal,
            "discount_percent": discount_percent,
            "discount_amount": discount_amount,
            "total": total,
            "seller_groups": [],
            "seller_count": 0,
        },
        status=status,
    )
def _attach_cart_badge_oob(request, response):
    badge_html = render_to_string("shopfront/partials/cart_badge_oob.html", _cart_badge_context(request), request=request)
    content = response.content.decode(response.charset or "utf-8")
    response.content = (content + badge_html).encode(response.charset or "utf-8")
    return response

from ..page_views import (
    HomeView,
    AboutPageView,
    DeliveryPageView,
    BuyersPageView,
    SuppliersPageView,
    PaymentPageView,
    ReturnsPageView,
    FaqPageView,
    ContactsPageView,
    BrandsPageView,
    BrandLegacyRedirectView,
    BrandDetailPageView,
    CategoryDetailPageView,
    CollectionsPageView,
    CollectionDetailPageView,
    PromotionsPageView,
    BlogPageView,
)
from ..checkout_views import (
    CartBadgeView,
    CartPanelView,
    CartAddView,
    BuyNowView,
    CartPageView,
    CartRemoveView,
    CartClearView,
    CartUpdateView,
    CheckoutPageView,
    CheckoutSubmitView,
    FakePaymentPageView,
    FakePaymentEventView,
    OnlinePaymentPageView,
    OnlinePaymentEventView,
    GuestOrderDetailView,
    GuestFakePaymentPageView,
    GuestFakePaymentEventView,
    GuestOnlinePaymentPageView,
    GuestOnlinePaymentEventView,
)
