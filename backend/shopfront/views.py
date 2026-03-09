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
    ProductReviewPhoto,
    ProductReviewVote,
    ProductQuestion,
    Collection,
    SellerOffer,
)
from catalog.offer_service import active_offer_queryset, apply_offer_snapshot, resolve_product_offer
from django.core.paginator import Paginator, EmptyPage
from django.views import View
from django.views.generic import TemplateView
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
from commerce.models import LegalEntityMembership, DeliveryAddress, SellerStore, StoreReview
from commerce.company_service import resolve_order_approval_requirement
from .forms import ContactFeedbackForm
from .models import (
    FavoriteProduct,
    SavedSearch,
    PersistentCart,
    CategorySubscription,
    BrandSubscription,
    RecentlyViewedProduct,
    SavedList,
    SavedListItem,
)
from .tasks import notify_contact_feedback
from .cart_store import persist_cart_for_user
from .cart_checkout_service import (
    cart_badge_context as _cart_badge_context,
    cart_summary as _cart_summary,
    checkout_addresses_queryset,
    checkout_cart_tracking_payload,
    checkout_company_snapshots,
    checkout_identity_defaults,
    profile_discount_percent as _profile_discount_percent,
    session_cart as _cart,
)
from .checkout_flow_service import (
    build_checkout_context as _build_checkout_context,
    ensure_checkout_idempotency_key,
    fake_payment_template_context,
)
from .catalog_selectors import (
    cached_catalog_default_page_ids as _cached_catalog_default_page_ids,
    cached_catalog_default_total_count as _cached_catalog_default_total_count,
    cached_home_category_ids as _cached_home_category_ids,
    cached_home_product_ids as _cached_home_product_ids,
    catalog_price_stats as _catalog_price_stats,
    category_breadcrumbs as _category_breadcrumbs,
    category_descendant_ids as _category_descendant_ids,
    category_option_rows as _category_option_rows,
    facet_option_counts as _facet_option_counts,
    ordered_products_with_related as _ordered_products_with_related,
    seller_facet_counts as _seller_facet_counts,
    with_rating as _with_rating,
)
from .search_service import get_search_provider, DatabaseSearchProvider, suggest_query_corrections
from .recommendations import (
    record_recent_view,
    recently_viewed_ids_for_user,
    frequently_bought_together_ids,
    seller_cross_sell_ids,
    personalized_home_sections,
    featured_collection_ids,
    brand_highlight_ids,
)
from .review_service import (
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
from .live_search_service import live_search_context
from .cart_mutation_service import (
    add_to_cart_session,
    clear_cart_session,
    remove_from_cart_session,
    update_cart_session,
)
from promotions.services import create_redemption, resolve_checkout_discount
import logging
import json
from uuid import uuid4
from django.utils import timezone
from core.logging_utils import log_calls
from decimal import Decimal
from . import search as sf_search
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
        "Disallow: /account/",
        f"Sitemap: https://{host}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


@log_calls(log)
def sitemap_xml(request):
    host = request.get_host().split(":")[0]
    base = f"https://{host}"
    static_paths = [
        reverse("home"),
        reverse("catalog"),
        reverse("buyers"),
        reverse("suppliers"),
        reverse("brands"),
        reverse("promotions"),
        reverse("blog"),
        reverse("about"),
        reverse("delivery"),
        reverse("payment"),
        reverse("returns"),
        reverse("faq"),
        reverse("contacts"),
        reverse("cart_page"),
        reverse("checkout"),
        reverse("twa_home"),
    ]
    urls = [base + path for path in static_paths]
    urls.extend(
        [base + reverse("product", kwargs={"slug": slug}) for slug in Product.objects.exclude(slug="").values_list("slug", flat=True)[:50000]]
    )
    urls.extend(
        [base + reverse("category_detail", kwargs={"category_slug": slug}) for slug in Category.objects.exclude(slug="").values_list("slug", flat=True)[:50000]]
    )
    urls.extend(
        [base + reverse("seller_store_detail", kwargs={"store_slug": slug}) for slug in SellerStore.objects.exclude(slug="").values_list("slug", flat=True)[:50000]]
    )
    urls.extend(
        [base + reverse("seller_profile", kwargs={"seller_slug": slug}) for slug in UserProfile.objects.exclude(slug="").values_list("slug", flat=True)[:50000]]
    )
    urls.extend(
        [base + reverse("brand_detail", kwargs={"brand_slug": slug}) for slug in Brand.objects.exclude(slug="").values_list("slug", flat=True)[:50000]]
    )
    urls.extend(
        [base + reverse("collection_detail", kwargs={"collection_slug": slug}) for slug in Collection.objects.filter(is_active=True).exclude(slug="").values_list("slug", flat=True)[:50000]]
    )

    body = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>", "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"]
    for loc in urls:
        body.append(f"  <url><loc>{escape(loc)}</loc></url>")
    body.append("</urlset>")
    return HttpResponse("\n".join(body), content_type="application/xml; charset=utf-8")


def _absolute_url(request, path: str) -> str:
    return request.build_absolute_uri(path)


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
            "target": f"{base}catalog/?q={{search_term_string}}",
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
            "url": _absolute_url(request, f"/product/{product.slug}/"),
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
    except Exception:
        return None
    if parsed < 0:
        return None
    return parsed.quantize(Decimal("0.01"))


def _new_idempotency_key() -> str:
    return uuid4().hex


def _new_guest_access_token() -> str:
    return uuid4().hex


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
    if expected and provided and expected == provided:
        return True
    return _guest_order_session_map(request).get(str(order.id), "") == expected and bool(expected)


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


def _tracking_item_from_product(product: Product, quantity: int = 1) -> dict:
    category_name = getattr(product.category, "name", "") or ""
    seller_store = getattr(getattr(product, "seller", None), "seller_store", None)
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
    if not products:
        return ""
    return json.dumps(
        {
            "event": "recommendation_impression",
            "recommendation_source": source,
            "ecommerce": {
                "item_list_name": source,
                "items": [_tracking_item_from_product(product) for product in products[:12]],
            },
        },
        ensure_ascii=False,
    )


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


def _seller_rating_summary(seller_id: int | None) -> dict:
    if not seller_id:
        return {"rating_avg": 0, "rating_count": 0}
    agg = ProductReview.objects.filter(product__seller_id=seller_id).aggregate(
        rating_avg=Coalesce(Avg("rating"), Value(0.0), output_field=FloatField()),
        rating_count=Count("id"),
    )
    return {
        "rating_avg": agg["rating_avg"] or 0,
        "rating_count": agg["rating_count"] or 0,
    }


def _store_rating_summary(store: SellerStore | None) -> dict:
    if store is None:
        return {"rating_avg": 0, "rating_count": 0}
    agg = StoreReview.objects.filter(store=store).aggregate(
        rating_avg=Coalesce(Avg("rating"), Value(0.0), output_field=FloatField()),
        rating_count=Count("id"),
    )
    return {
        "rating_avg": agg["rating_avg"] or 0,
        "rating_count": agg["rating_count"] or 0,
    }


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
        except Exception:
            continue
        if product_id not in ids:
            ids.append(product_id)
    return ids[:COMPARE_LIMIT]


def _set_compare_ids(request, product_ids: list[int]) -> list[int]:
    normalized: list[int] = []
    for product_id in product_ids:
        try:
            candidate = int(product_id)
        except Exception:
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
        {"label": "Магазин", "values": [getattr(getattr(product.seller, "seller_store", None), "name", "—") or "—" for product in products]},
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
            except Exception:
                order.status = Order.Status.CONFIRMED
            order.save(update_fields=["status"])
        if order.status == Order.Status.CONFIRMED:
            try:
                order.pay()
            except Exception:
                order.status = Order.Status.PAID
            order.save(update_fields=["status"])
    elif next_status in {FakeAcquiringPayment.Status.FAILED, FakeAcquiringPayment.Status.CANCELED}:
        if order.status not in {Order.Status.CANCELED, Order.Status.DELIVERED}:
            try:
                order.cancel()
            except Exception:
                order.status = Order.Status.CANCELED
            order.save(update_fields=["status"])
    elif next_status == FakeAcquiringPayment.Status.REFUNDED:
        if order.status not in {Order.Status.CANCELED, Order.Status.DELIVERED}:
            try:
                order.mark_changed()
            except Exception:
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

@method_decorator(ensure_csrf_cookie, name="dispatch")
class HomeView(TemplateView):
    template_name = "shopfront/home.html"
    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cat_ids = _cached_home_category_ids(limit=8)
        ctx["cats"] = list(Category.objects.filter(id__in=cat_ids).order_by("name"))
        product_ids = _cached_home_product_ids(limit=12)
        ctx["products"] = _ordered_products_with_related(product_ids)
        personalized = personalized_home_sections(self.request.user, limit=8)
        ctx["featured_collections"] = list(Collection.objects.filter(id__in=featured_collection_ids(limit=3)))
        ctx["featured_brands"] = list(
            Brand.objects.filter(id__in=brand_highlight_ids(limit=6))
            .annotate(
                products_count=Count("products", distinct=True),
                categories_count=Count("products__category", distinct=True),
            )
            .order_by("-products_count", "name")
        )
        ctx["recommended_for_you"] = _ordered_products_with_related(personalized["for_you"], include_rating=True)
        ctx["home_recently_viewed"] = _ordered_products_with_related(personalized["based_on_lists"], include_rating=True)
        ctx["watchlist_products"] = _ordered_products_with_related(personalized["brand_watch"], include_rating=True)
        ctx["recommended_for_you_tracking_payload"] = _recommendation_impression_payload("home_for_you", ctx["recommended_for_you"])
        ctx["home_recently_viewed_tracking_payload"] = _recommendation_impression_payload("home_recently_viewed", ctx["home_recently_viewed"])
        ctx["watchlist_products_tracking_payload"] = _recommendation_impression_payload("home_watchlist", ctx["watchlist_products"])
        ctx.update(
            _seo_context(
                self.request,
                title="Servio — маркетплейс товаров для HoReCa",
                description="Servio объединяет поставщиков товаров для ресторанов, кафе, баров, отелей и кейтеринга в одном удобном b2b-каталоге.",
                json_ld=[_website_json_ld(self.request), _organization_json_ld(self.request)],
            )
        )
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class AboutPageView(TemplateView):
    template_name = "shopfront/about.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            _seo_context(
                self.request,
                title="О платформе Servio",
                description="Servio — маркетплейс товаров для HoReCa с понятной логикой закупки, единым каталогом поставщиков и современным b2b-сервисом.",
            )
        )
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class DeliveryPageView(TemplateView):
    template_name = "shopfront/delivery.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            _seo_context(
                self.request,
                title="Доставка и логистика — Servio",
                description="Условия доставки заказов Servio: график отгрузок, работа по регионам, документооборот и логистика для HoReCa-команд.",
            )
        )
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class BuyersPageView(TemplateView):
    template_name = "shopfront/buyers.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            _seo_context(
                self.request,
                title="Для покупателей — Servio",
                description="Как закупать через Servio: поиск товаров, согласование ассортимента, адреса доставки, повтор заказов и работа с несколькими поставщиками.",
            )
        )
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class SuppliersPageView(TemplateView):
    template_name = "shopfront/suppliers.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            _seo_context(
                self.request,
                title="Для поставщиков — Servio",
                description="Servio помогает поставщикам HoReCa продавать через единый маркетплейс: управление ассортиментом, новые клиенты и прозрачный вход в b2b-канал.",
            )
        )
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class PaymentPageView(TemplateView):
    template_name = "shopfront/payment.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            _seo_context(
                self.request,
                title="Оплата — Servio",
                description="Форматы оплаты на Servio: безналичный расчет, оплата по счету и прозрачный документооборот для b2b-клиентов.",
            )
        )
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class ReturnsPageView(TemplateView):
    template_name = "shopfront/returns.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            _seo_context(
                self.request,
                title="Возврат и обмен — Servio",
                description="Правила возврата и обмена на Servio: приемка товара, фиксация расхождений и порядок обработки претензий для HoReCa-заказов.",
            )
        )
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class FaqPageView(TemplateView):
    template_name = "shopfront/faq.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            _seo_context(
                self.request,
                title="FAQ — Servio",
                description="Частые вопросы о работе Servio: регистрация, каталог, доставка, оплата, статусы заказов и работа с поставщиками.",
            )
        )
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class ContactsPageView(TemplateView):
    template_name = "shopfront/contacts.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form"] = kwargs.get("form") or ContactFeedbackForm()
        ctx.update(
            _seo_context(
                self.request,
                title="Контакты Servio",
                description="Контакты Servio: поддержка клиентов, связь по закупкам, сопровождение поставщиков и рабочие каналы команды платформы.",
            )
        )
        return ctx

    @log_calls(log)
    def post(self, request, *args, **kwargs):
        form = ContactFeedbackForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form), status=400)

        cleaned = form.cleaned_data
        notify_contact_feedback.delay(
            name=cleaned["name"],
            phone=cleaned["phone"],
            message=cleaned["message"],
            source=request.build_absolute_uri("/contacts/"),
        )
        messages.success(request, "Спасибо. Мы получили заявку и свяжемся с вами.")
        return redirect("/contacts/")


@method_decorator(ensure_csrf_cookie, name="dispatch")
class BrandsPageView(TemplateView):
    template_name = "shopfront/brands.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        brands = list(
            Brand.objects.annotate(
                products_count=Count("products", distinct=True),
                categories_count=Count("products__category", distinct=True),
                collections_count=Count("products__collections", distinct=True),
            )
            .only("id", "name", "slug", "description", "photo")
            .order_by("-products_count", "name")
        )
        ctx["brands"] = brands
        ctx.update(
            _seo_context(
                self.request,
                title="Бренды — Servio",
                description="Коллекция брендов HoReCa в каталоге Servio: посуда, стекло, бар, сервировка, упаковка и расходные материалы.",
            )
        )
        return ctx


class BrandLegacyRedirectView(View):
    @log_calls(log)
    def get(self, request, brand_id: int):
        brand = get_object_or_404(Brand, pk=brand_id)
        return redirect("brand_detail", brand_slug=brand.slug)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class BrandDetailPageView(TemplateView):
    template_name = "shopfront/brand_detail.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        brand = get_object_or_404(
            Brand.objects.annotate(
                products_count=Count("products", distinct=True),
                categories_count=Count("products__category", distinct=True),
                collections_count=Count("products__collections", distinct=True),
            ),
            slug=kwargs["brand_slug"],
        )
        product_ids = list(
            Product.objects.filter(brand=brand).order_by("-is_new", "name").values_list("id", flat=True)[:60]
        )
        ctx["brand"] = brand
        ctx["products"] = _ordered_products_with_related(product_ids, include_rating=True)
        ctx["child_categories"] = list(
            Category.objects.filter(products__brand=brand).distinct().order_by("name")[:8]
        )
        ctx["featured_collections"] = list(
            Collection.objects.filter(is_active=True, items__product__brand=brand)
            .distinct()
            .order_by("-is_featured", "name")[:4]
        )
        ctx["is_brand_subscribed"] = bool(
            self.request.user.is_authenticated
            and BrandSubscription.objects.filter(user=self.request.user, brand=brand).exists()
        )
        ctx.update(
            _seo_context(
                self.request,
                title=f"{brand.name} — каталог бренда | Servio",
                description=_truncate_text(brand.description or f"Ассортимент бренда {brand.name} в каталоге Servio для профессиональных закупок HoReCa.", 160),
                canonical=_absolute_url(self.request, reverse("brand_detail", kwargs={"brand_slug": brand.slug})),
            )
        )
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CategoryDetailPageView(TemplateView):
    template_name = "shopfront/category_detail.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        category = get_object_or_404(Category.objects.select_related("parent"), slug=kwargs["category_slug"])
        category_ids = _category_descendant_ids(category)
        product_ids = list(
            Product.objects.filter(category_id__in=category_ids).order_by("-is_new", "name").values_list("id", flat=True)[:80]
        )
        ctx["category"] = category
        ctx["products"] = _ordered_products_with_related(product_ids, include_rating=True)
        ctx["breadcrumbs"] = _category_breadcrumbs(category)
        ctx["child_categories"] = list(category.children.order_by("name")[:12])
        ctx["featured_brands"] = list(
            Brand.objects.filter(products__category_id__in=category_ids).distinct().order_by("name")[:8]
        )
        ctx.update(
            _seo_context(
                self.request,
                title=f"{category.meta_title or category.name} — категория Servio",
                description=_truncate_text(category.meta_description or category.description or category.hero_text or f"Категория {category.name} в каталоге Servio.", 160),
                canonical=_absolute_url(self.request, reverse("category_detail", kwargs={"category_slug": category.slug})),
            )
        )
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CollectionsPageView(TemplateView):
    template_name = "shopfront/collections.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["collections"] = list(Collection.objects.filter(is_active=True).order_by("-is_featured", "name"))
        ctx.update(
            _seo_context(
                self.request,
                title="Коллекции и подборки — Servio",
                description="Кураторские коллекции и готовые подборки Servio для сезонных закупок, промо-кампаний и repeat purchase сценариев.",
            )
        )
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CollectionDetailPageView(TemplateView):
    template_name = "shopfront/collection_detail.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        collection = get_object_or_404(Collection.objects.filter(is_active=True), slug=kwargs["collection_slug"])
        product_ids = list(collection.items.order_by("ordering", "id").values_list("product_id", flat=True)[:80])
        ctx["collection"] = collection
        ctx["products"] = _ordered_products_with_related(product_ids, include_rating=True)
        ctx["related_collections"] = list(
            Collection.objects.filter(is_active=True, is_featured=True).exclude(id=collection.id).order_by("-updated_at", "name")[:3]
        )
        ctx.update(
            _seo_context(
                self.request,
                title=f"{collection.name} — коллекция Servio",
                description=_truncate_text(collection.description or collection.hero_text or f"Коллекция {collection.name} в Servio.", 160),
                canonical=_absolute_url(self.request, reverse("collection_detail", kwargs={"collection_slug": collection.slug})),
            )
        )
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class PromotionsPageView(TemplateView):
    template_name = "shopfront/promotions.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        product_ids = list(
            Product.objects.filter(is_promo=True).order_by("-is_new", "name").values_list("id", flat=True)[:40]
        )
        ctx["products"] = _ordered_products_with_related(product_ids, include_rating=True)
        ctx.update(
            _seo_context(
                self.request,
                title="Спецпредложения — Servio",
                description="Подборка акционных и сезонных позиций Servio для ресторанов, кафе, баров, гостиниц и кейтеринга.",
            )
        )
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class BlogPageView(TemplateView):
    template_name = "shopfront/blog.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["posts"] = [
            {
                "title": "Как закупать расходники для HoReCa без каскада ручных таблиц",
                "slug": "horeca-procurement-playbook",
                "excerpt": "Практический подход к планированию закупок, который снижает простои и out-of-stock.",
                "tag": "Операции",
            },
            {
                "title": "Чек-лист контроля ассортимента для b2b-магазина",
                "slug": "assortment-control-checklist",
                "excerpt": "Какие показатели отслеживать в первую очередь: маржа, оборачиваемость, SLA поставки.",
                "tag": "Аналитика",
            },
            {
                "title": "Как выстроить политику скидок без просадки маржи",
                "slug": "promo-margin-guide",
                "excerpt": "Сценарии промо-кампаний, которые дают рост повторных заказов без демпинга.",
                "tag": "Маркетинг",
            },
        ]
        ctx.update(
            _seo_context(
                self.request,
                title="Журнал Servio",
                description="Материалы Servio о закупках для HoReCa, управлении ассортиментом, работе с поставщиками и b2b-операциях.",
            )
        )
        return ctx


class FavoriteToggleView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request):
        product_id = request.POST.get("product_id")
        if not str(product_id or "").isdigit():
            return JsonResponse({"ok": False, "error": "invalid product_id"}, status=400)
        product = get_object_or_404(Product, pk=int(product_id))
        obj, created = FavoriteProduct.objects.get_or_create(user=request.user, product=product)
        if not created:
            obj.delete()
        return JsonResponse(
            {
                "ok": True,
                "favorited": created,
                "tracking": {
                    "event": "wishlist_add" if created else "wishlist_remove",
                    "ecommerce": {"items": [_tracking_item_from_product(product)]},
                },
            }
        )


class SubscriptionToggleView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request):
        entity = (request.POST.get("entity") or "").strip()
        entity_id = request.POST.get("entity_id")
        if not str(entity_id or "").isdigit():
            return JsonResponse({"ok": False, "error": "invalid entity_id"}, status=400)

        model_map = {
            "brand": (BrandSubscription, Brand, "brand"),
            "category": (CategorySubscription, Category, "category"),
        }
        if entity not in model_map:
            return JsonResponse({"ok": False, "error": "invalid entity"}, status=400)

        subscription_model, source_model, fk_name = model_map[entity]
        source = get_object_or_404(source_model, pk=int(entity_id))
        lookup = {"user": request.user, fk_name: source}
        obj, created = subscription_model.objects.get_or_create(**lookup)
        if not created:
            obj.delete()

        return JsonResponse(
            {
                "ok": True,
                "subscribed": created,
                "entity": entity,
                "entity_id": int(entity_id),
            }
        )


class CompareToggleView(View):
    @log_calls(log)
    def post(self, request):
        product_id = request.POST.get("product_id")
        if not str(product_id or "").isdigit():
            return JsonResponse({"ok": False, "error": "invalid product_id"}, status=400)
        product = get_object_or_404(Product.objects.only("id", "name", "slug", "price"), pk=int(product_id))
        product_id_int = int(product_id)
        compare_ids = _compare_ids(request)
        added = False
        if product_id_int in compare_ids:
            compare_ids = [pid for pid in compare_ids if pid != product_id_int]
        else:
            compare_ids = [product_id_int] + [pid for pid in compare_ids if pid != product_id_int]
            compare_ids = compare_ids[:COMPARE_LIMIT]
            added = True
        compare_ids = _set_compare_ids(request, compare_ids)
        return JsonResponse(
            {
                "ok": True,
                "in_compare": added,
                "compare_count": len(compare_ids),
                "compare_ids": compare_ids,
                "tracking": {
                    "event": "compare_add" if added else "compare_remove",
                    "ecommerce": {"items": [_tracking_item_from_product(product)]},
                },
            }
        )


class ComparePageView(TemplateView):
    template_name = "shopfront/compare.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        products = _ordered_products_with_related(_compare_ids(self.request), include_rating=True)
        ctx["products"] = products
        ctx["compare_rows"] = _compare_fields(products)
        ctx.update(
            _seo_context(
                self.request,
                title="Сравнение товаров — Servio",
                description="Сравнение товаров по цене, бренду, серии, наличию, срокам поставки и ключевым характеристикам.",
                canonical=_absolute_url(self.request, reverse("compare_page")),
                robots="noindex,follow",
            )
        )
        return ctx


class FavoritesPageView(LoginRequiredMixin, TemplateView):
    template_name = "shopfront/favorites.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        product_ids = list(
            FavoriteProduct.objects.filter(user=self.request.user)
            .order_by("-created_at")
            .values_list("product_id", flat=True)[:300]
        )
        ctx["products"] = _ordered_products_with_related(product_ids, include_rating=True)
        ctx["category_subscriptions"] = (
            CategorySubscription.objects.select_related("category")
            .filter(user=self.request.user)
            .order_by("-created_at")[:12]
        )
        ctx["brand_subscriptions"] = (
            BrandSubscription.objects.select_related("brand")
            .filter(user=self.request.user)
            .order_by("-created_at")[:12]
        )
        ctx["saved_lists"] = _saved_list_queryset(self.request.user)[:8]
        ctx.update(
            _seo_context(
                self.request,
                title="Избранное — Servio",
                description="Список сохранённых товаров в аккаунте Servio.",
                robots="noindex,nofollow",
            )
        )
        return ctx


class SavedListsPageView(LoginRequiredMixin, TemplateView):
    template_name = "shopfront/saved_lists.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    @log_calls(log)
    def post(self, request, *args, **kwargs):
        action = (request.POST.get("action") or "").strip()
        if action == "create":
            name = (request.POST.get("name") or "").strip() or "Новый список"
            description = (request.POST.get("description") or "").strip()
            SavedList.objects.create(user=request.user, name=name[:140], description=description[:255])
            messages.success(request, "Список создан")
        elif action == "delete":
            list_id = request.POST.get("list_id")
            if str(list_id or "").isdigit():
                SavedList.objects.filter(user=request.user, id=int(list_id)).delete()
                messages.success(request, "Список удалён")
        elif action == "create_from_favorites":
            product_ids = list(
                FavoriteProduct.objects.filter(user=request.user).order_by("-created_at").values_list("product_id", flat=True)[:80]
            )
            if product_ids:
                saved_list = SavedList.objects.create(user=request.user, name="Из избранного", source=SavedList.Source.FAVORITES)
                _saved_list_add_products(saved_list, product_ids)
                messages.success(request, "Список из избранного создан")
        elif action == "create_from_cart":
            cart = _cart(request)
            product_ids = []
            quantities = {}
            for raw_id, payload in cart.items():
                if str(raw_id).isdigit():
                    product_id = int(raw_id)
                    product_ids.append(product_id)
                    quantities[product_id] = max(1, int((payload or {}).get("qty") or 1))
            if product_ids:
                saved_list = SavedList.objects.create(user=request.user, name="Текущая корзина", source=SavedList.Source.CART)
                _saved_list_add_products(saved_list, product_ids, quantities=quantities)
                messages.success(request, "Корзина сохранена как список")
        return redirect("saved_lists")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["saved_lists"] = _saved_list_queryset(self.request.user)[:100]
        ctx["favorites_count"] = FavoriteProduct.objects.filter(user=self.request.user).count()
        ctx["cart_items_count"] = sum(max(0, int(item.get("qty", 0) or 0)) for item in _cart(self.request).values())
        ctx.update(
            _seo_context(
                self.request,
                title="Списки закупок — Servio",
                description="Сохранённые списки для repeat purchase, подготовки закупок и шаринга подборок внутри команды.",
                robots="noindex,nofollow",
            )
        )
        return ctx


class SavedListDetailView(LoginRequiredMixin, TemplateView):
    template_name = "shopfront/saved_list_detail.html"

    def _get_list(self):
        return get_object_or_404(
            SavedList.objects.prefetch_related("items__product__images", "items__product__brand", "items__product__seller__seller_store"),
            user=self.request.user,
            id=self.kwargs["list_id"],
        )

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    @log_calls(log)
    def post(self, request, *args, **kwargs):
        saved_list = self._get_list()
        action = (request.POST.get("action") or "").strip()
        if action == "toggle_public":
            saved_list.is_public = not saved_list.is_public
            saved_list.save(update_fields=["is_public", "updated_at"])
            messages.success(request, "Настройки доступа обновлены")
        elif action == "move_to_cart":
            for item in saved_list.items.select_related("product").all():
                _cart_add_product(request, item.product_id, qty=item.quantity)
            messages.success(request, "Список добавлен в корзину")
        elif action == "remove_item":
            item_id = request.POST.get("item_id")
            if str(item_id or "").isdigit():
                SavedListItem.objects.filter(saved_list=saved_list, id=int(item_id)).delete()
                messages.success(request, "Товар удалён из списка")
        return redirect("saved_list_detail", list_id=saved_list.id)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        saved_list = self._get_list()
        product_ids = list(saved_list.items.values_list("product_id", flat=True))
        ctx["saved_list"] = saved_list
        ctx["products"] = _ordered_products_with_related(product_ids, include_rating=True)
        ctx["share_url"] = _absolute_url(self.request, reverse("saved_list_shared", kwargs={"share_token": saved_list.share_token}))
        ctx.update(
            _seo_context(
                self.request,
                title=f"{saved_list.name} — список закупок Servio",
                description=_truncate_text(saved_list.description or f"Список {saved_list.name} в Servio.", 160),
                robots="noindex,nofollow",
            )
        )
        return ctx


class SharedSavedListView(TemplateView):
    template_name = "shopfront/saved_list_shared.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        saved_list = get_object_or_404(
            SavedList.objects.prefetch_related("items__product__images", "items__product__brand"),
            share_token=kwargs["share_token"],
            is_public=True,
        )
        ctx["saved_list"] = saved_list
        ctx["products"] = _ordered_products_with_related(
            list(saved_list.items.values_list("product_id", flat=True)),
            include_rating=True,
        )
        ctx.update(
            _seo_context(
                self.request,
                title=f"{saved_list.name} — публичный список Servio",
                description=_truncate_text(saved_list.description or f"Публичный список {saved_list.name} в Servio.", 160),
            )
        )
        return ctx


class SavedListFromOrderView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, order_id: int):
        order = get_object_or_404(Order.objects.prefetch_related("items"), id=order_id, placed_by=request.user)
        saved_list = SavedList.objects.create(
            user=request.user,
            name=f"Повтор заказа #{order.id}",
            description="Список, сформированный из ранее оформленного заказа",
            source=SavedList.Source.ORDER,
        )
        quantities = {item.product_id: item.qty for item in order.items.all()}
        _saved_list_add_products(saved_list, list(quantities.keys()), quantities=quantities)
        messages.success(request, "Заказ сохранён как список")
        return redirect("saved_list_detail", list_id=saved_list.id)


class SavedSearchesPageView(LoginRequiredMixin, TemplateView):
    template_name = "shopfront/saved_searches.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    @log_calls(log)
    def post(self, request, *args, **kwargs):
        action = (request.POST.get("action") or "").strip()
        if action == "save":
            querystring = (request.POST.get("querystring") or "").strip()
            name = (request.POST.get("name") or "").strip() or "Мой фильтр"
            if querystring:
                SavedSearch.objects.create(
                    user=request.user,
                    name=name[:120],
                    querystring=querystring[:512],
                )
                messages.success(request, "Поиск сохранён")
        elif action == "delete":
            sid = request.POST.get("id")
            if str(sid or "").isdigit():
                SavedSearch.objects.filter(user=request.user, id=int(sid)).delete()
                messages.success(request, "Сохранённый поиск удалён")
        return redirect("saved_searches")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["saved_searches"] = SavedSearch.objects.filter(user=self.request.user).order_by("-created_at")[:200]
        ctx.update(
            _seo_context(
                self.request,
                title="Сохранённые поиски — Servio",
                description="Ваши сохранённые фильтры и поисковые запросы.",
                robots="noindex,nofollow",
            )
        )
        return ctx

@method_decorator(ensure_csrf_cookie, name="dispatch")
class CatalogView(View):
    @log_calls(log)
    def get(self, request):
        get_token(request)
        qs = Product.objects.all()
        brand = request.GET.get("brand")
        category = request.GET.get("category")
        seller = request.GET.get("seller")
        series = request.GET.get("series")
        q = request.GET.get("q","")
        tag = request.GET.get("tag") or request.GET.get("tag_slug")
        availability = (request.GET.get("availability") or "").strip()
        delivery_eta = (request.GET.get("delivery_eta") or "").strip()
        min_price = _parse_decimal_filter(request.GET.get("min_price"))
        max_price = _parse_decimal_filter(request.GET.get("max_price"))
        sort = (request.GET.get("sort") or "").strip()
        try:
            page = int(request.GET.get("page") or 1)
        except (TypeError, ValueError):
            page = 1
        if page < 1:
            page = 1
        page_size = 16
        selected_category_obj = None
        selected_seller_store = None
        selected_series_obj = None
        if brand:
            if str(brand).isdigit():
                qs = qs.filter(brand_id=int(brand))
            else:
                qs = qs.none()
        if series:
            if str(series).isdigit():
                from catalog.models import Series
                selected_series_obj = Series.objects.select_related("brand").filter(id=int(series)).only("id", "name", "brand_id", "brand__name", "brand__slug").first()
            if selected_series_obj:
                qs = qs.filter(series_id=selected_series_obj.id)
            else:
                qs = qs.none()
        if category:
            if str(category).isdigit():
                selected_category_obj = Category.objects.select_related("parent").filter(id=int(category)).first()
            else:
                selected_category_obj = Category.objects.select_related("parent").filter(slug=category).first()
            if selected_category_obj:
                qs = qs.filter(category_id__in=_category_descendant_ids(selected_category_obj))
            else:
                qs = qs.none()
        es_ranked_ids = []
        search_suggestions: list[str] = []
        if q:
            max_hits = int(getattr(settings, "ES_CATALOG_MAX_HITS", 2000))
            try:
                bundle = get_search_provider().live_bundle(query=q, limit=max_hits, country_limit=0)
                es_ranked_ids = bundle.product_ids
                search_suggestions = bundle.suggestions[:8]
            except sf_search.ESSearchUnavailable:
                fallback_bundle = DatabaseSearchProvider().live_bundle(query=q, limit=max_hits, country_limit=0)
                es_ranked_ids = fallback_bundle.product_ids
                search_suggestions = fallback_bundle.suggestions[:8]
            if not search_suggestions:
                search_suggestions = suggest_query_corrections(q, limit=6)
            if not es_ranked_ids:
                qs = qs.none()
            else:
                qs = qs.filter(id__in=es_ranked_ids)
        if tag:
            if tag.isdigit():
                qs = qs.filter(tags__id=int(tag))
            else:
                qs = qs.filter(tags__slug=tag)
        if seller:
            if str(seller).isdigit():
                qs = qs.filter(Q(seller_id=int(seller)) | Q(seller_offers__seller_id=int(seller), seller_offers__status=SellerOffer.Status.ACTIVE))
                selected_seller_store = SellerStore.objects.filter(owner_id=int(seller)).only("name", "slug", "owner_id").first()
            else:
                selected_seller_store = SellerStore.objects.filter(slug=seller).only("name", "slug", "owner_id").first()
                if selected_seller_store:
                    qs = qs.filter(
                        Q(seller_id=selected_seller_store.owner_id)
                        | Q(seller_offers__seller_id=selected_seller_store.owner_id, seller_offers__status=SellerOffer.Status.ACTIVE)
                    )
                else:
                    qs = qs.none()
        if availability == "in_stock":
            qs = qs.filter(
                Q(stock_qty__gt=0)
                | Q(seller_offers__status=SellerOffer.Status.ACTIVE, seller_offers__inventories__stock_qty__gt=0)
            )
        if delivery_eta == "fast":
            qs = qs.filter(Q(lead_time_days__lte=2) | Q(seller_offers__status=SellerOffer.Status.ACTIVE, seller_offers__lead_time_days__lte=2))
        elif delivery_eta == "week":
            qs = qs.filter(
                Q(lead_time_days__gt=2, lead_time_days__lte=7)
                | Q(seller_offers__status=SellerOffer.Status.ACTIVE, seller_offers__lead_time_days__gt=2, seller_offers__lead_time_days__lte=7)
            )
        elif delivery_eta == "planned":
            qs = qs.filter(Q(lead_time_days__gt=7) | Q(seller_offers__status=SellerOffer.Status.ACTIVE, seller_offers__lead_time_days__gt=7))
        if min_price is not None:
            qs = qs.filter(Q(price__gte=min_price) | Q(seller_offers__status=SellerOffer.Status.ACTIVE, seller_offers__price__gte=min_price))
        if max_price is not None:
            qs = qs.filter(Q(price__lte=max_price) | Q(seller_offers__status=SellerOffer.Status.ACTIVE, seller_offers__price__lte=max_price))
        qs = qs.distinct()
        facet_seed_qs = qs
        sort_map = {
            "new": ["-is_new", "name", "id"],
            "price_asc": ["price", "name", "id"],
            "price_desc": ["-price", "name", "id"],
            "name": ["name", "id"],
            "promo": ["-is_promo", "name", "id"],
            "rating_desc": ["-rating_avg", "-rating_count", "name", "id"],
        }
        include_rating = bool(getattr(settings, "ENABLE_CATALOG_RATING", settings.DEBUG))
        default_catalog = not any([brand, category, seller, series, q, tag, availability, delivery_eta, min_price, max_price]) and (not sort or sort == "new")
        cacheable_default_catalog = (
            default_catalog
            and page == 1
            and not request.user.is_authenticated
            and not request.headers.get("HX-Request")
            and not (request.session.get("cart") or {})
            and not (request.session.get(COMPARE_SESSION_KEY) or [])
        )
        if cacheable_default_catalog:
            cached_html = _cache_get("shopfront:catalog:html:v1:default")
            if cached_html:
                return HttpResponse(cached_html)
        if sort == "rating_desc":
            qs = _with_rating(qs).order_by(*sort_map["rating_desc"])
        elif q and es_ranked_ids and not sort:
            rank_order = Case(
                *[When(id=pid, then=pos) for pos, pid in enumerate(es_ranked_ids)],
                default=len(es_ranked_ids),
                output_field=IntegerField(),
            )
            qs = qs.order_by(rank_order)
        else:
            qs = qs.order_by(*sort_map.get(sort, ["-is_new", "name", "id"]))
        if default_catalog:
            total_count = _cached_catalog_default_total_count()
            num_pages = max(1, (total_count + page_size - 1) // page_size)
            safe_page = min(page, num_pages)
            page_ids = _cached_catalog_default_page_ids(page=safe_page, page_size=page_size)
            products_page = _ordered_products_with_related(page_ids, include_rating=include_rating)
            has_next = safe_page < num_pages
            next_page = safe_page + 1 if has_next else None
            current_page = safe_page
        else:
            paginator = Paginator(qs.values_list("id", flat=True), page_size)
            try:
                page_obj = paginator.page(page)
            except EmptyPage:
                page_obj = paginator.page(paginator.num_pages or 1)
            page_ids = list(page_obj.object_list)
            products_page = _ordered_products_with_related(page_ids, include_rating=include_rating)
            total_count = paginator.count
            has_next = page_obj.has_next()
            next_page = page_obj.next_page_number() if page_obj.has_next() else None
            current_page = page_obj.number
        base_params = {}
        if q:
            base_params["q"] = q
        if brand:
            base_params["brand"] = brand
        if category:
            base_params["category"] = category
        if seller:
            base_params["seller"] = seller
        if series:
            base_params["series"] = series
        if tag:
            base_params["tag"] = tag
        if delivery_eta:
            base_params["delivery_eta"] = delivery_eta
        if sort:
            base_params["sort"] = sort
        querystring_base = urlencode(base_params)
        category_reset_params = {k: v for k, v in base_params.items() if k != "category"}
        category_reset_querystring = urlencode(category_reset_params)
        category_reset_url = f"/catalog/?{category_reset_querystring}" if category_reset_querystring else "/catalog/"
        if request.headers.get("HX-Request") and request.GET.get("fragment") == "grid_append":
            return render(request, "shopfront/partials/catalog_grid_append.html", {
                "products": products_page,
                "has_next": has_next,
                "next_page": next_page,
                "querystring_base": querystring_base,
            })
        brands = _cache_get("shopfront:catalog:brands:v1")
        if brands is None:
            brands = list(Brand.objects.only("id", "name").order_by("name"))
            _cache_set("shopfront:catalog:brands:v1", brands, timeout=getattr(settings, "CACHE_TTL_CATALOG_FILTERS", 900))
        cats = _cache_get("shopfront:catalog:categories:v1")
        if cats is None:
            cats = list(
                Category.objects.select_related("parent")
                .exclude(name__startswith="HoReCa направление")
                .only("id", "name", "slug", "parent_id")
                .order_by("parent_id", "name", "id")
            )
            _cache_set("shopfront:catalog:categories:v1", cats, timeout=getattr(settings, "CACHE_TTL_CATALOG_FILTERS", 900))
        category_rows = _category_option_rows(cats)
        tags = _cache_get("shopfront:catalog:tags:v1")
        if tags is None:
            tags = list(Tag.objects.only("id", "name", "slug").order_by("name")[:50])
            _cache_set("shopfront:catalog:tags:v1", tags, timeout=getattr(settings, "CACHE_TTL_CATALOG_FILTERS", 900))
        brand_id = int(brand) if brand and str(brand).isdigit() else None
        sel_brand = next((b for b in brands if brand_id is not None and b.id == brand_id), None)
        if category:
            sel_category = selected_category_obj or (next((c for c in cats if str(category).isdigit() and c.id == int(category)), None) if str(category).isdigit() else next((c for c in cats if c.slug == category), None))
        else:
            sel_category = None
        selected_category_children = [item for item in cats if sel_category and item.parent_id == sel_category.id][:8]
        facet_brand_options = _facet_option_counts(
            facet_seed_qs.exclude(brand_id=int(brand)) if brand and str(brand).isdigit() else facet_seed_qs,
            "brand",
            label_field="name",
            limit=10,
        )
        facet_seller_options = _seller_facet_counts(
            facet_seed_qs.exclude(seller_id=int(seller)) if seller and str(seller).isdigit() else facet_seed_qs,
            limit=10,
        )
        facet_price_stats = _catalog_price_stats(facet_seed_qs)
        fallback_product_ids = []
        if total_count == 0:
            fallback_product_ids = list(
                Product.objects.order_by("-is_promo", "-is_new", "name").values_list("id", flat=True)[:8]
            )
        is_category_subscribed = bool(
            request.user.is_authenticated
            and sel_category is not None
            and CategorySubscription.objects.filter(user=request.user, category=sel_category).exists()
        )
        is_category_only = bool(category) and not any([q, brand, series, tag, sort, availability, delivery_eta, min_price, max_price]) and page == 1
        seo_robots = "index,follow" if (not any([q, brand, seller, series, tag, sort, availability, delivery_eta, min_price, max_price]) and page == 1) or is_category_only else "noindex,follow"
        if is_category_only:
            seo_canonical = _absolute_url(request, f"/catalog/?{urlencode({'category': category})}")
            category_name = sel_category.name if sel_category else str(category)
            seo_title = f"{category_name} — каталог Servio"
            seo_description = f"Товары категории «{category_name}» в каталоге Servio для HoReCa-закупок."
        else:
            seo_canonical = _absolute_url(request, "/catalog/")
            seo_title = "Каталог товаров для HoReCa — Servio"
            seo_description = "Каталог Servio: посуда, стекло, барный инвентарь, сервировка, упаковка, текстиль и расходные материалы для HoReCa."
        context = {
            "products": products_page,
            "brands": brands,
            "cats": cats,
            "category_rows": category_rows,
            "tags": tags,
            "sort": sort or "new",
            "q": q,
            "brand": brand,
            "category": category,
            "tag": tag,
            "availability": availability,
            "delivery_eta": delivery_eta,
            "min_price": min_price,
            "max_price": max_price,
            "seller": seller,
            "series": series,
            "has_next": has_next,
            "next_page": next_page,
            "querystring_base": querystring_base,
            "total_count": total_count,
            "page": current_page,
            "page_size": page_size,
            "sel_brand": sel_brand,
            "sel_category": sel_category,
            "sel_seller_store": selected_seller_store,
            "sel_series": selected_series_obj,
            "is_category_subscribed": is_category_subscribed,
            "selected_category_children": selected_category_children,
            "facet_brand_options": facet_brand_options,
            "facet_seller_options": facet_seller_options,
            "facet_price_min": facet_price_stats.get("min_price"),
            "facet_price_max": facet_price_stats.get("max_price"),
            "zero_results_products": _ordered_products_with_related(fallback_product_ids, include_rating=True),
            "category_breadcrumbs": _category_breadcrumbs(sel_category),
            "category_reset_url": category_reset_url,
            "catalog_tracking_payload": json.dumps(
                {
                    "event": "search" if q else "filter_use",
                    "search_term": q,
                    "filters": {
                        "brand": brand or "",
                        "category": getattr(sel_category, "slug", "") if sel_category else "",
                        "seller": getattr(selected_seller_store, "slug", "") if selected_seller_store else "",
                        "series": getattr(selected_series_obj, "name", "") if selected_series_obj else "",
                        "tag": tag or "",
                        "availability": availability or "",
                        "delivery_eta": delivery_eta or "",
                        "min_price": str(min_price or ""),
                        "max_price": str(max_price or ""),
                        "sort": sort or "new",
                    },
                    "ecommerce": {
                        "item_list_name": "catalog",
                        "items": [_tracking_item_from_product(p) for p in products_page[:12]],
                    },
                    "results_count": total_count,
                    "search_recovery_shown": bool(total_count == 0 and (search_suggestions or q)),
                },
                ensure_ascii=False,
            ) if any([q, brand, category, tag, availability, delivery_eta, min_price, max_price, sort]) else "",
            "search_suggestions": [item for item in search_suggestions if item.casefold() != q.casefold()][:6],
            "search_corrections": [] if total_count else suggest_query_corrections(q, limit=4),
            **_seo_context(
                request,
                title=seo_title,
                description=seo_description,
                canonical=seo_canonical,
                robots=seo_robots,
            ),
        }
        if cacheable_default_catalog:
            html = render_to_string("shopfront/catalog.html", context, request=request)
            _cache_set("shopfront:catalog:html:v1:default", html, timeout=20)
            return HttpResponse(html)
        return render(request, "shopfront/catalog.html", context)


class LiveSearchView(View):
    @log_calls(log)
    def get(self, request):
        return render(
            request,
            "shopfront/partials/live_search_results.html",
            live_search_context(query=request.GET.get("q"), search_provider_getter=get_search_provider, logger=log),
        )


@method_decorator(ensure_csrf_cookie, name="dispatch")
class ProductDetailView(TemplateView):
    template_name = "shopfront/product_detail.html"
    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        slug = kwargs.get("slug")
        p = get_object_or_404(
            Product.objects.select_related(
                "brand",
                "series",
                "category",
                "category__parent",
                "seller",
                "seller__seller_store",
            ).prefetch_related(
                Prefetch(
                    "images",
                    queryset=ProductImage.objects.only("id", "product_id", "url", "alt", "ordering").order_by("ordering", "id"),
                    to_attr="prefetched_images",
                ),
                "tags",
                "documents",
                "collections",
                Prefetch("seller_offers", queryset=active_offer_queryset()),
            ),
            slug=slug,
        )
        apply_offer_snapshot([p])
        _record_recently_viewed(self.request, p)
        ctx.update(build_reviews_context(p, self.request.user, seller_rating_summary=_seller_rating_summary))
        seller_store = getattr(getattr(p, "active_offer", None), "seller_store", None) or (getattr(p.seller, "seller_store", None) if p.seller_id else None)
        seller_summary = _seller_rating_summary(getattr(p, "seller_id", None))
        store_summary = _store_rating_summary(seller_store)
        ctx["seller_store"] = seller_store
        ctx["active_offer"] = getattr(p, "active_offer", None)
        ctx["product_documents"] = list(p.documents.all())
        ctx["product_collections"] = list(p.collections.all()[:6])
        ctx["breadcrumbs"] = _category_breadcrumbs(getattr(p, "category", None))
        ctx["compare_included"] = p.id in _compare_ids(self.request)
        ctx["store_rating_avg"] = store_summary["rating_avg"]
        ctx["store_rating_count"] = store_summary["rating_count"]
        ctx["seller_rating_avg"] = seller_summary["rating_avg"]
        ctx["seller_rating_count"] = seller_summary["rating_count"]
        ctx["is_brand_subscribed"] = bool(
            self.request.user.is_authenticated
            and p.brand_id
            and BrandSubscription.objects.filter(user=self.request.user, brand_id=p.brand_id).exists()
        )
        ctx["is_category_subscribed"] = bool(
            self.request.user.is_authenticated
            and p.category_id
            and CategorySubscription.objects.filter(user=self.request.user, category_id=p.category_id).exists()
        )
        similar_ids: list[int] = []
        if p.category_id:
            similar_ids.extend(
                list(
                    Product.objects.filter(category_id=p.category_id)
                    .exclude(id=p.id)
                    .order_by("-is_promo", "-is_new", "name", "id")
                    .values_list("id", flat=True)[:12]
                )
            )
        if len(similar_ids) < 12 and p.brand_id:
            more_ids = list(
                Product.objects.filter(brand_id=p.brand_id)
                .exclude(id=p.id)
                .exclude(id__in=similar_ids)
                .order_by("-is_promo", "-is_new", "name", "id")
                .values_list("id", flat=True)[: 12 - len(similar_ids)]
            )
            similar_ids.extend(more_ids)
        ctx["similar_products"] = _ordered_products_with_related(similar_ids[:12], include_rating=True)
        accessory_ids: list[int] = []
        if p.seller_id:
            accessory_ids.extend(
                list(
                    Product.objects.filter(seller_id=p.seller_id)
                    .exclude(id__in=[p.id] + similar_ids)
                    .order_by("-is_promo", "-is_new", "name", "id")
                    .values_list("id", flat=True)[:8]
                )
            )
        if len(accessory_ids) < 8 and p.tags.exists():
            accessory_ids.extend(
                list(
                    Product.objects.filter(tags__in=p.tags.all())
                    .exclude(id__in=[p.id] + similar_ids + accessory_ids)
                    .distinct()
                    .order_by("-is_promo", "-is_new", "name", "id")
                    .values_list("id", flat=True)[: 8 - len(accessory_ids)]
                )
            )
        ctx["accessory_products"] = _ordered_products_with_related(accessory_ids[:8], include_rating=True)
        ctx["recently_viewed_products"] = _recently_viewed_products(self.request, exclude_product_id=p.id, limit=8)
        ctx["frequently_bought_together_products"] = _ordered_products_with_related(
            frequently_bought_together_ids(p, limit=8),
            include_rating=True,
        )
        ctx["seller_cross_sell_products"] = _ordered_products_with_related(
            seller_cross_sell_ids(p, limit=8),
            include_rating=True,
        )
        ctx["frequently_bought_together_tracking_payload"] = _recommendation_impression_payload(
            "product_frequently_bought_together",
            ctx["frequently_bought_together_products"],
        )
        ctx["seller_cross_sell_tracking_payload"] = _recommendation_impression_payload(
            "product_seller_cross_sell",
            ctx["seller_cross_sell_products"],
        )
        ctx["saved_lists"] = _saved_list_queryset(self.request.user)[:8] if self.request.user.is_authenticated else []
        ctx["product_tracking_payload"] = json.dumps(
            {
                "event": "product_view",
                "ecommerce": {
                    "currency": "RUB",
                    "value": float(p.display_price),
                    "items": [_tracking_item_from_product(p)],
                },
            },
            ensure_ascii=False,
        )
        ctx["is_favorite"] = bool(
            self.request.user.is_authenticated
            and FavoriteProduct.objects.filter(user=self.request.user, product=p).exists()
        )
        ctx["can_edit_product"] = bool(
            self.request.user.is_authenticated
            and (
                self.request.user.is_staff
                or self.request.user.is_superuser
                or p.seller_id == self.request.user.id
            )
        )
        primary_image = _product_primary_image(p)
        ctx.update(
            _seo_context(
                self.request,
                title=f"{p.name} — {getattr(p.brand, 'name', 'Servio')} | Servio",
                description=_truncate_text(p.description or f"{p.name} в каталоге Servio: поставки для ресторанов, кафе, баров и гостиничных проектов.", 170),
                canonical=_absolute_url(self.request, f"/product/{p.slug}/"),
                og_type="product",
                og_image=_absolute_url(self.request, primary_image.url) if primary_image else _default_og_image(self.request),
                json_ld=_product_json_ld(self.request, p, seller_store=seller_store),
            )
        )
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class SellerStoreDetailView(TemplateView):
    template_name = "shopfront/store_detail.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        store_slug = kwargs.get("store_slug")
        store_qs = SellerStore.objects.select_related("owner", "owner__profile", "legal_entity")
        store = store_qs.filter(slug=store_slug).first()
        if store is None:
            raise Http404("Store not found")
        product_ids = list(
            Product.objects.filter(seller=store.owner).order_by("-is_new", "name").values_list("id", flat=True)[:60]
        )
        products = _ordered_products_with_related(product_ids, include_rating=True)
        ctx.update({"store": store, "products": products, "store_rating": _store_rating_summary(store)})
        ctx.update(_store_reviews_context(store, self.request.user))
        ctx.update(
            _seo_context(
                self.request,
                title=f"{store.name} — витрина поставщика | Servio",
                description=f"Ассортимент магазина {store.name} на Servio: поставщик товаров для HoReCa, актуальные позиции и профессиональный каталог.",
            )
        )
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class SellerProfileView(TemplateView):
    template_name = "shopfront/seller_profile.html"
    seller_user = None

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        User = get_user_model()
        seller_slug = kwargs.get("seller_slug")
        seller_user = User.objects.select_related("profile").filter(profile__slug=seller_slug).first()
        if seller_user is None:
            legacy_user = User.objects.select_related("profile").filter(username=seller_slug).first()
            if legacy_user is not None:
                return redirect("seller_profile", seller_slug=legacy_user.profile.slug, permanent=True)
            raise Http404("Seller not found")
        self.seller_user = seller_user
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        seller_user = self.seller_user
        if seller_user is None:
            raise Http404("Seller not found")
        memberships = LegalEntityMembership.objects.select_related("legal_entity", "role").filter(user=seller_user)
        stores = SellerStore.objects.select_related("legal_entity").filter(owner=seller_user).order_by("name")
        seller_rating = _seller_rating_summary(seller_user.id)
        ctx.update(
            {
                "seller_user": seller_user,
                "seller_profile": seller_user.profile,
                "memberships": memberships,
                "stores": stores,
                "seller_rating": seller_rating,
            }
        )
        display_name = seller_user.profile.full_name or seller_user.username
        ctx.update(
            _seo_context(
                self.request,
                title=f"{display_name} — профиль поставщика | Servio",
                description=f"Профиль поставщика {display_name} на Servio: магазины, юридические данные и ассортимент для HoReCa.",
            )
        )
        return ctx


class SellerStoreLegacyRedirectView(View):
    @log_calls(log)
    def get(self, request, store_id: int):
        store = get_object_or_404(SellerStore, pk=store_id)
        return redirect("seller_store_detail", store_slug=store.slug, permanent=True)


class SellerProfileLegacyRedirectView(View):
    @log_calls(log)
    def get(self, request, username: str):
        User = get_user_model()
        seller_user = User.objects.select_related("profile").filter(username=username).first()
        if seller_user is None:
            raise Http404("Seller not found")
        return redirect("seller_profile", seller_slug=seller_user.profile.slug, permanent=True)


class StoreReviewUpsertView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, store_slug):
        store = get_object_or_404(SellerStore, slug=store_slug)
        raw_rating = (request.POST.get("rating") or "").strip()
        text = (request.POST.get("text") or "").strip()
        try:
            rating = int(raw_rating)
        except Exception:
            rating = 0
        if rating < 1 or rating > 5:
            messages.error(request, "Рейтинг магазина должен быть от 1 до 5")
            return redirect("seller_store_detail", store_slug=store.slug)

        has_verified_purchase = OrderItem.objects.filter(
            order__placed_by=request.user,
            order__status__in=[Order.Status.CONFIRMED, Order.Status.PAID, Order.Status.DELIVERING, Order.Status.DELIVERED, Order.Status.CHANGED],
            product__seller=store.owner,
        ).exists()
        StoreReview.objects.update_or_create(
            store=store,
            user=request.user,
            defaults={"rating": rating, "text": text, "is_verified_buyer": has_verified_purchase},
        )
        messages.success(request, "Отзыв о магазине сохранён")
        return redirect(f"{reverse('seller_store_detail', kwargs={'store_slug': store.slug})}#store-reviews")


class StoreReviewDeleteView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, store_slug):
        store = get_object_or_404(SellerStore, slug=store_slug)
        deleted, _ = StoreReview.objects.filter(store=store, user=request.user).delete()
        if deleted:
            messages.success(request, "Отзыв о магазине удалён")
        return redirect(f"{reverse('seller_store_detail', kwargs={'store_slug': store.slug})}#store-reviews")


class ProductPkRedirectView(View):
    @log_calls(log)
    def get(self, request, pk):
        p = get_object_or_404(Product, pk=pk)
        return redirect(f"/product/{p.slug}/", permanent=True)


class ProductReviewUpsertView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, slug):
        p = get_object_or_404(Product, slug=slug)
        raw_rating = (request.POST.get("rating") or "").strip()
        text = (request.POST.get("text") or "").strip()
        try:
            rating = int(raw_rating)
        except Exception:
            rating = 0
        if rating < 1 or rating > 5:
            if request.headers.get("HX-Request"):
                return render_reviews_partial(request, p, seller_rating_summary=_seller_rating_summary, status=400)
            messages.error(request, "Рейтинг должен быть от 1 до 5")
            return redirect(f"/product/{p.slug}/#reviews")
        upsert_product_review(product=p, user=request.user, rating=rating, text=text)
        context = build_reviews_context(p, request.user, seller_rating_summary=_seller_rating_summary)

        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        messages.success(request, "Отзыв сохранен")
        return redirect(f"/product/{p.slug}/#reviews")


class ProductReviewDeleteView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, slug):
        p = get_object_or_404(Product, slug=slug)
        deleted = delete_product_review(product=p, user=request.user)
        if deleted:
            messages.success(request, "Отзыв удален")
        context = build_reviews_context(p, request.user, seller_rating_summary=_seller_rating_summary)
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"/product/{p.slug}/#reviews")


class ProductReviewCommentCreateView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, slug, review_id):
        p = get_object_or_404(Product, slug=slug)
        review = get_object_or_404(ProductReview, pk=review_id, product=p)
        text = (request.POST.get("text") or "").strip()
        if not text:
            if request.headers.get("HX-Request"):
                return render_reviews_partial(request, p, seller_rating_summary=_seller_rating_summary, status=400)
            return redirect(f"/product/{p.slug}/#reviews")
        create_review_comment(review=review, user=request.user, text=text)
        context = build_reviews_context(p, request.user, seller_rating_summary=_seller_rating_summary)
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"/product/{p.slug}/#reviews")


class ProductReviewCommentUpdateView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, slug, comment_id):
        p = get_object_or_404(Product, slug=slug)
        comment = get_object_or_404(ProductReviewComment.objects.select_related("review"), pk=comment_id, review__product=p)
        if comment.user_id != request.user.id:
            if request.headers.get("HX-Request"):
                return render_reviews_partial(request, p, seller_rating_summary=_seller_rating_summary, status=403)
            return HttpResponse(status=403)
        text = (request.POST.get("text") or "").strip()
        if not text:
            if request.headers.get("HX-Request"):
                return render_reviews_partial(request, p, seller_rating_summary=_seller_rating_summary, status=400)
            return redirect(f"/product/{p.slug}/#reviews")
        update_review_comment(comment=comment, text=text)
        context = build_reviews_context(p, request.user, seller_rating_summary=_seller_rating_summary)
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"/product/{p.slug}/#reviews")


class ProductReviewCommentDeleteView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, slug, comment_id):
        p = get_object_or_404(Product, slug=slug)
        comment = get_object_or_404(ProductReviewComment.objects.select_related("review"), pk=comment_id, review__product=p)
        if comment.user_id != request.user.id:
            if request.headers.get("HX-Request"):
                return render_reviews_partial(request, p, seller_rating_summary=_seller_rating_summary, status=403)
            return HttpResponse(status=403)
        delete_review_comment(comment=comment)
        context = build_reviews_context(p, request.user, seller_rating_summary=_seller_rating_summary)
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"/product/{p.slug}/#reviews")


class ProductReviewVoteView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, slug, review_id):
        p = get_object_or_404(Product, slug=slug)
        review = get_object_or_404(ProductReview, pk=review_id, product=p)
        value = (request.POST.get("value") or "").strip()
        if value not in {ProductReviewVote.Value.HELPFUL, ProductReviewVote.Value.UNHELPFUL}:
            if request.headers.get("HX-Request"):
                return render_reviews_partial(request, p, seller_rating_summary=_seller_rating_summary, status=400)
            return redirect(f"/product/{p.slug}/#reviews")
        apply_review_vote(review=review, user=request.user, value=value)
        context = build_reviews_context(p, request.user, seller_rating_summary=_seller_rating_summary)
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"/product/{p.slug}/#reviews")


class ProductQuestionCreateView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, slug):
        p = get_object_or_404(Product, slug=slug)
        question_text = (request.POST.get("question_text") or "").strip()
        if not question_text:
            if request.headers.get("HX-Request"):
                return render_reviews_partial(request, p, seller_rating_summary=_seller_rating_summary, status=400)
            return redirect(f"/product/{p.slug}/#questions")
        create_product_question(product=p, user=request.user, question_text=question_text)
        context = build_reviews_context(p, request.user, seller_rating_summary=_seller_rating_summary)
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        messages.success(request, "Вопрос отправлен")
        return redirect(f"/product/{p.slug}/#questions")

@method_decorator(ensure_csrf_cookie, name="dispatch")
class TwaHomeView(TemplateView):
    template_name = "shopfront/twa_home.html"
    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        product_ids = _cached_home_product_ids(limit=12)
        ctx["products"] = _ordered_products_with_related(product_ids)
        ctx.update(
            _seo_context(
                self.request,
                title="Telegram Web App — Servio",
                description="Telegram Web App Servio для быстрых b2b-заказов.",
                robots="noindex,nofollow",
            )
        )
        return ctx

class CartBadgeView(TemplateView):
    template_name = "shopfront/partials/cart_badge.html"
    @log_calls(log)
    def get(self, request, *args, **kwargs):
        resp = render(
            request,
            self.template_name,
            _cart_badge_context(request),
        )
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return resp

class CartPanelView(TemplateView):
    template_name = "shopfront/partials/cart_panel.html"
    @log_calls(log)
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, _cart_summary(request))

class CartAddView(View):
    @log_calls(log)
    def post(self, request):
        try:
            pid = int(request.POST.get("product_id"))
            qty = int(request.POST.get("qty", 1))
        except Exception:
            return JsonResponse({"ok": False, "error": "invalid_payload"}, status=400)
        try:
            mutation = add_to_cart_session(request=request, product_id=pid, qty=qty, logger=log)
        except Product.DoesNotExist:
            log.warning("cart_add_product_not_found", extra={"product_id": pid})
            return JsonResponse({"ok": False, "error": "product_not_found"}, status=404)
        log.info("cart_add", extra={"product_id": pid, "qty": qty})
        triggers = json.dumps({
            "showToast": {"message": "Товар добавлен в корзину", "variant": "success"},
            "cartChanged": {},
            "cartQtyUpdated": {"product_id": pid, "qty": mutation["current_qty"]},
            "analyticsEvent": {
                "event": "add_to_cart",
                "ecommerce": {
                    "currency": "RUB",
                    "value": float(mutation["line_value"]),
                    "items": [_tracking_item_from_product(mutation["product"], quantity=max(1, qty))],
                },
            },
        })
        resp = HttpResponse("", status=200)
        resp["HX-Trigger"] = triggers
        resp["HX-Trigger-After-Settle"] = triggers
        return _attach_cart_badge_oob(request, resp)


class BuyNowView(View):
    @log_calls(log)
    def post(self, request):
        try:
            pid = int(request.POST.get("product_id"))
            qty = int(request.POST.get("qty", 1))
        except Exception:
            messages.error(request, "Не удалось подготовить быстрый заказ")
            return redirect("catalog")
        try:
            add_to_cart_session(request=request, product_id=pid, qty=qty, logger=log)
        except Product.DoesNotExist:
            log.warning("buy_now_product_not_found", extra={"product_id": pid})
            messages.error(request, "Товар не найден")
            return redirect("catalog")
        log.info("buy_now", extra={"product_id": pid, "qty": qty})
        return redirect("checkout")

class CartPageView(TemplateView):
    template_name = "shopfront/cart.html"
    @log_calls(log)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_cart_summary(self.request))
        cart_product_ids = [item["p"].id for item in ctx.get("items", [])]
        seller_ids = [item["p"].seller_id for item in ctx.get("items", []) if item["p"].seller_id]
        cross_sell_ids = list(
            Product.objects.filter(seller_id__in=seller_ids)
            .exclude(id__in=cart_product_ids)
            .order_by("-is_promo", "-is_new", "name")
            .values_list("id", flat=True)[:8]
        )
        ctx["cart_recommendations"] = _ordered_products_with_related(cross_sell_ids, include_rating=True)
        ctx["cart_recommendations_tracking_payload"] = _recommendation_impression_payload("cart_cross_sell", ctx["cart_recommendations"])
        ctx.update(
            _seo_context(
                self.request,
                title="Корзина — Servio",
                description="Корзина пользователя Servio.",
                robots="noindex,nofollow",
            )
        )
        return ctx

class CartRemoveView(View):
    @log_calls(log)
    def post(self, request):
        pid = request.POST.get("product_id")
        remove_from_cart_session(request=request, product_id=pid)
        log.info("cart_remove", extra={"product_id": pid})
        cart_ctx = _cart_summary(request)
        resp = render(request, "shopfront/partials/cart_content.html" if (request.headers.get("HX-Target") or "").strip() == "cart-root" else "shopfront/partials/cart_panel.html", cart_ctx)
        try:
            pid_int = int(pid)
        except Exception:
            pid_int = None
        payload = {
            "showToast": {"message": "Удалено из корзины", "variant": "danger"},
            "cartChanged": {},
        }
        if pid_int is not None:
            payload["cartQtyUpdated"] = {"product_id": pid_int, "qty": 0}
        resp["HX-Trigger"] = json.dumps(payload)
        return _attach_cart_badge_oob(request, resp)

class CartClearView(View):
    @log_calls(log)
    def post(self, request):
        clear_cart_session(request=request)
        log.info("cart_clear")
        cart_ctx = _cart_summary(request)
        resp = render(request, "shopfront/partials/cart_content.html" if (request.headers.get("HX-Target") or "").strip() == "cart-root" else "shopfront/partials/cart_panel.html", cart_ctx)
        resp["HX-Trigger"] = '{"showToast": {"message": "Корзина очищена", "variant": "danger"}, "cartChanged": {}}'
        return _attach_cart_badge_oob(request, resp)

class CartUpdateView(View):
    @log_calls(log)
    def post(self, request):
        pid = request.POST.get("product_id")
        op = (request.POST.get("op") or "").strip()
        try:
            pid_int = int(pid)
        except Exception:
            return JsonResponse({"ok": False, "error": "invalid_product"}, status=400)
        mutation = update_cart_session(
            request=request,
            product_id=pid_int,
            op=op,
            requested_qty=request.POST.get("qty", 1),
            logger=log,
        )
        if mutation["missing"]:
            return render(request, "shopfront/partials/cart_content.html", _cart_summary(request), status=404)
        log.info("cart_update", extra={"product_id": pid_int, "op": op, "qty": mutation["qty"]})
        cart_ctx = _cart_summary(request)
        resp = render(request, "shopfront/partials/cart_content.html" if (request.headers.get("HX-Target") or "").strip() == "cart-root" else "shopfront/partials/cart_panel.html", cart_ctx)
        resp["HX-Trigger"] = json.dumps({
            "showToast": {"message": "Количество обновлено", "variant": "success"},
            "cartChanged": {},
            "cartQtyUpdated": {"product_id": pid_int, "qty": mutation["qty"]},
        })
        return _attach_cart_badge_oob(request, resp)


class CheckoutPageView(TemplateView):
    template_name = "shopfront/checkout.html"
    @log_calls(log)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_checkout_context(self.request))
        checkout_product_ids = [item["p"].id for item in ctx.get("items", [])]
        checkout_seller_ids = [item["p"].seller_id for item in ctx.get("items", []) if item["p"].seller_id]
        checkout_reco_ids = list(
            Product.objects.filter(seller_id__in=checkout_seller_ids)
            .exclude(id__in=checkout_product_ids)
            .order_by("-is_promo", "-is_new", "name")
            .values_list("id", flat=True)[:6]
        )
        ctx["checkout_recommendations"] = _ordered_products_with_related(checkout_reco_ids, include_rating=True)
        ctx["checkout_recommendations_tracking_payload"] = _recommendation_impression_payload(
            "checkout_cross_sell",
            ctx["checkout_recommendations"],
        )
        ctx["begin_checkout_tracking_payload"] = json.dumps(
            {
                "event": "begin_checkout",
                **_checkout_items_payload(ctx["items"], ctx["total"], ctx["seller_count"]),
            },
            ensure_ascii=False,
        ) if ctx["items"] else ""
        ctx.update(
            _seo_context(
                self.request,
                title="Оформление заказа — Servio",
                description="Оформление заказа на Servio.",
                robots="noindex,nofollow",
            )
        )
        return ctx


class CheckoutSubmitView(View):
    @log_calls(log)
    def post(self, request):
        is_hx = bool(request.headers.get("HX-Request"))

        def fail(msg):
            if is_hx:
                ctx = _checkout_context(request, form_data=request.POST, checkout_error=msg)
                return render(request, "shopfront/partials/checkout_form_panel.html", ctx, status=422)
            messages.error(request, msg)
            return redirect("checkout")

        # Idempotency (optional, per user)
        from core.models import IdempotencyKey
        idem_key = request.headers.get("X-Idempotency-Key") or request.POST.get("_idem")
        user_id = request.user.id if request.user.is_authenticated else 0
        if idem_key:
            key_obj, created = IdempotencyKey.create_or_get(user_id=user_id, route="checkout_submit", key=idem_key, ttl_sec=600)
            if not created:
                log.info("checkout_idempotent_reused", extra={"user_id": user_id or 0, "key": idem_key})
                if is_hx:
                    return fail("Заказ уже оформлен")
                messages.info(request, "Заказ уже оформлен")
                return redirect("checkout")
        cust_type = request.POST.get("customer_type") or Order.CustomerType.COMPANY
        pay_method = request.POST.get("payment_method") or Order.PaymentMethod.CASH
        customer_comment = (request.POST.get("customer_comment") or "").strip()
        coupon_code = (request.POST.get("coupon_code") or "").strip()
        source_channel = Order.SourceChannel.TWA if request.path.startswith("/twa") else Order.SourceChannel.WEB
        # Build product list from cart
        cart = _cart(request)
        if not cart:
            return fail("Корзина пуста")
        ids = []
        for raw_id in cart.keys():
            try:
                ids.append(int(raw_id))
            except Exception:
                continue
        products = {
            p.id: p
            for p in Product.objects.select_related("brand", "category", "series", "seller", "seller__seller_store")
            .prefetch_related(Prefetch("seller_offers", queryset=active_offer_queryset()))
            .filter(id__in=ids)
        }
        apply_offer_snapshot(products.values())
        if not products:
            return fail("Товары не найдены")
        checkout_lines = []
        # Stock validation
        for pid, item in cart.items():
            try:
                pid_int = int(pid)
            except Exception:
                continue
            p = products.get(pid_int)
            if not p:
                continue
            req_qty = max(1, int(item.get("qty") or 1))
            if p.display_stock_qty is not None and int(p.display_stock_qty) >= 0 and req_qty > int(p.display_stock_qty):
                log.info("checkout_stock_insufficient", extra={"product_id": p.id, "name": p.name, "requested": req_qty, "stock": int(p.display_stock_qty)})
                return fail(f"Недостаточно на складе для товара: {p.name}")
            checkout_lines.append({"product": p, "qty": req_qty, "row_total": Decimal(str(p.display_price)) * Decimal(req_qty)})
        guest_email = (request.POST.get("customer_email") or "").strip().lower()
        with transaction.atomic():
            discount_result = resolve_checkout_discount(
                user=request.user,
                customer_type=cust_type,
                coupon_code=coupon_code,
                guest_email=guest_email,
                lines=checkout_lines,
                lock=True,
            )
            if discount_result.error:
                return fail(discount_result.error)
            # Create order depending on type
            if cust_type == Order.CustomerType.COMPANY:
                if not request.user.is_authenticated:
                    return fail("Для оформления B2B-заказа войдите в аккаунт компании")
                le_id = request.POST.get("legal_entity")
                addr_id = request.POST.get("delivery_address")
                if not le_id or not addr_id:
                    return fail("Выберите юр лицо и адрес доставки")
                if not LegalEntityMembership.objects.filter(user=request.user, legal_entity_id=le_id).exists():
                    return fail("Нет доступа к выбранному юрлицу")
                try:
                    DeliveryAddress.objects.get(pk=addr_id, legal_entity_id=le_id)
                except DeliveryAddress.DoesNotExist:
                    return fail("Адрес не принадлежит юрлицу")
                order = Order.objects.create(
                    customer_type=Order.CustomerType.COMPANY,
                    payment_method=pay_method,
                    legal_entity_id=le_id,
                    delivery_address_id=addr_id,
                    placed_by=request.user,
                    requested_by=request.user,
                    customer_comment=customer_comment,
                    coupon_code=discount_result.coupon.code if discount_result.coupon else "",
                    source_channel=source_channel,
                )
                approval = resolve_order_approval_requirement(
                    legal_entity=order.legal_entity,
                    user=request.user,
                    order_total=Decimal("0.00"),
                )
                log.info("order_created_company", extra={"order_id": order.id, "le_id": le_id, "addr_id": addr_id})
            else:
                fallback_name = ""
                if request.user.is_authenticated:
                    fallback_name = request.user.get_full_name() or request.user.username
                name = (request.POST.get("customer_name") or "").strip() or fallback_name
                email = (request.POST.get("customer_email") or "").strip().lower()
                phone = (request.POST.get("customer_phone") or "").strip()
                addr = (request.POST.get("address_text") or "").strip()
                if not request.user.is_authenticated and not email:
                    return fail("Укажите email для гостевого заказа")
                if not phone or not addr:
                    return fail("Укажите телефон и адрес доставки")
                guest_token = _new_guest_access_token() if not request.user.is_authenticated else ""
                order = Order.objects.create(
                    customer_type=Order.CustomerType.INDIVIDUAL,
                    payment_method=pay_method,
                    customer_name=name,
                    customer_email=email or getattr(request.user, "email", ""),
                    customer_phone=phone,
                    address_text=addr,
                    placed_by=request.user if request.user.is_authenticated else None,
                    guest_access_token=guest_token,
                    customer_comment=customer_comment,
                    coupon_code=discount_result.coupon.code if discount_result.coupon else "",
                    source_channel=source_channel,
                )
                log.info("order_created_individual", extra={"order_id": order.id})
            # Create items
            items = []
            for pid, item in cart.items():
                try:
                    pid_int = int(pid)
                except Exception:
                    continue
                p = products.get(pid_int)
                if not p:
                    continue
                qty = int(item["qty"]) or 1
                items.append(
                    OrderItem(
                        order=order,
                        product=p,
                        seller_offer=getattr(p, "active_offer", None),
                        name=p.name,
                        price=p.display_price,
                        qty=qty,
                    )
                )
            OrderItem.objects.bulk_create(items)
            order.recalc_totals(explicit_discount_amount=discount_result.total_discount_amount)
            if cust_type == Order.CustomerType.COMPANY:
                approval = resolve_order_approval_requirement(
                    legal_entity=order.legal_entity,
                    user=request.user,
                    order_total=order.total,
                )
                order.approval_status = (
                    Order.ApprovalStatus.PENDING if approval.requires_approval else Order.ApprovalStatus.APPROVED
                )
            order.save(update_fields=["subtotal","discount_amount","total","approval_status"])
            if cust_type == Order.CustomerType.COMPANY:
                OrderApprovalLog.objects.create(
                    order=order,
                    actor=request.user,
                    decision=OrderApprovalLog.Decision.REQUESTED,
                    comment=approval.reason if approval.requires_approval else "Авто-согласование по политике компании",
                )
            create_redemption(
                order=order,
                discount_result=discount_result,
                user=request.user,
                guest_email=guest_email,
            )
        request.session["cart"] = {}
        request.session["checkout_idem_key"] = _new_idempotency_key()
        request.session.modified = True
        if order.is_guest:
            _remember_guest_order(request, order)
        else:
            PersistentCart.objects.update_or_create(user=request.user, defaults={"payload": {}})
        if pay_method == Order.PaymentMethod.MIR_CARD:
            provider = get_payment_provider(pay_method)
            provider_result = provider.initialize(order) if provider else None
            payment = provider_result.payment if provider_result else FakeAcquiringPayment.objects.get(order=order)
            if not payment.history:
                _append_payment_history(
                    payment,
                    FakeAcquiringPayment.Event.START,
                    FakeAcquiringPayment.Status.PROCESSING,
                    note="Симуляция эквайринга запущена",
                )
                payment.save(update_fields=["history", "status", "last_event", "updated_at"])
            if is_hx:
                resp = render(
                    request,
                    "shopfront/partials/fake_payment_panel.html",
                    {
                        "order": order,
                        "payment": payment,
                        "order_detail_url": _order_detail_url(order),
                        "payment_event_url": _fake_payment_event_url(order),
                        "payment_page_url": _fake_payment_page_url(order),
                    },
                )
                resp["HX-Trigger"] = json.dumps(
                    {
                        "showToast": {"message": f"Заказ #{order.id} создан. Запущен тест эквайринга", "variant": "success"},
                        "cartChanged": {},
                        "analyticsEvent": _payment_tracking_payload("payment_started", order, payment, payment_event=FakeAcquiringPayment.Event.START),
                    }
                )
                return resp
            messages.info(request, f"Заказ #{order.id} создан. Откройте симулятор оплаты.")
            return redirect(_fake_payment_page_url(order))
        if is_hx:
            resp = render(
                request,
                "shopfront/partials/checkout_success_panel.html",
                {
                    "order": order,
                    "order_detail_url": _order_detail_url(order),
                },
            )
            resp["HX-Trigger"] = json.dumps({
                "showToast": {"message": f"Заказ #{order.id} оформлен", "variant": "success"},
                "cartChanged": {},
                "analyticsEvent": _order_tracking_payload(order),
            })
            return resp
        messages.success(request, f"Заказ #{order.id} оформлен")
        return redirect(_order_detail_url(order))


class FakePaymentPageView(TemplateView):
    template_name = "shopfront/fake_payment.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        order = get_object_or_404(Order.objects.select_related("placed_by"), pk=kwargs["order_id"], placed_by=request.user)
        payment = get_object_or_404(FakeAcquiringPayment, order=order)
        return render(
            request,
            self.template_name,
            fake_payment_template_context(
                order=order,
                payment=payment,
                order_detail_url=_order_detail_url(order),
                payment_event_url=_fake_payment_event_url(order),
                payment_started_tracking_payload=json.dumps(
                    _payment_tracking_payload("payment_started", order, payment, payment_event=payment.last_event),
                    ensure_ascii=False,
                ),
            ),
        )


class FakePaymentEventView(View):
    @log_calls(log)
    def post(self, request, order_id):
        order = get_object_or_404(Order.objects.select_related("placed_by"), pk=order_id, placed_by=request.user)
        payment = get_object_or_404(FakeAcquiringPayment, order=order)
        event = (request.POST.get("event") or "").strip()
        allowed = {x[0] for x in FakeAcquiringPayment.Event.choices}
        if event not in allowed:
            return HttpResponse("Unknown event", status=400)
        _apply_fake_payment_event(order, payment, event)
        payment.refresh_from_db()
        order.refresh_from_db()
        trigger_payload = {
            "showToast": {
                "message": f"Событие: {_payment_event_label(event)}",
                "variant": "success" if payment.status == FakeAcquiringPayment.Status.PAID else "warning",
            }
        }
        if payment.status == FakeAcquiringPayment.Status.PAID:
            trigger_payload["analyticsEvent"] = _order_tracking_payload(order)
        elif event in {FakeAcquiringPayment.Event.FAIL, FakeAcquiringPayment.Event.CANCEL}:
            trigger_payload["analyticsEvent"] = _payment_tracking_payload("payment_failed", order, payment, payment_event=event)
        response = render(
            request,
            "shopfront/partials/fake_payment_panel.html",
            fake_payment_template_context(
                order=order,
                payment=payment,
                order_detail_url=_order_detail_url(order),
                payment_event_url=_fake_payment_event_url(order),
                payment_page_url=_fake_payment_page_url(order),
            ),
        )
        response["HX-Trigger"] = json.dumps(trigger_payload)
        return response


class GuestOrderDetailView(TemplateView):
    template_name = "shopfront/guest_order_detail.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        order = get_object_or_404(
            Order.objects.select_related("legal_entity", "delivery_address", "placed_by").prefetch_related(
                Prefetch(
                    "items",
                    queryset=OrderItem.objects.select_related("product", "seller_offer").prefetch_related(
                        Prefetch(
                            "product__images",
                            queryset=ProductImage.objects.only("id", "product_id", "url", "alt", "ordering").order_by("ordering", "id"),
                            to_attr="prefetched_images",
                        )
                    ),
                ),
                "seller_splits",
                "seller_orders",
                "seller_orders__items",
                "seller_orders__items__product",
                "seller_orders__items__seller_offer",
                "seller_orders__shipments",
                "seller_orders__shipments__items",
            ),
            pk=kwargs["order_id"],
        )
        token = (kwargs.get("token") or "").strip()
        if not _has_guest_order_access(request, order, token=token):
            raise Http404("Order not found")
        if order.is_guest:
            _remember_guest_order(request, order)
        return render(
            request,
            self.template_name,
            {
                "order": order,
                "fake_payment": getattr(order, "fake_payment", None),
                "order_detail_url": _order_detail_url(order),
                "payment_page_url": _fake_payment_page_url(order),
            },
        )


class GuestFakePaymentPageView(TemplateView):
    template_name = "shopfront/fake_payment.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        order = get_object_or_404(Order.objects.select_related("placed_by"), pk=kwargs["order_id"])
        token = (kwargs.get("token") or "").strip()
        if not _has_guest_order_access(request, order, token=token):
            raise Http404("Order not found")
        payment = get_object_or_404(FakeAcquiringPayment, order=order)
        if order.is_guest:
            _remember_guest_order(request, order)
        return render(
            request,
            self.template_name,
            fake_payment_template_context(
                order=order,
                payment=payment,
                order_detail_url=_order_detail_url(order),
                payment_event_url=_fake_payment_event_url(order),
                payment_started_tracking_payload=json.dumps(
                    _payment_tracking_payload("payment_started", order, payment, payment_event=payment.last_event),
                    ensure_ascii=False,
                ),
            ),
        )


class GuestFakePaymentEventView(View):
    @log_calls(log)
    def post(self, request, order_id, token):
        order = get_object_or_404(Order.objects.select_related("placed_by"), pk=order_id)
        if not _has_guest_order_access(request, order, token=(token or "").strip()):
            raise Http404("Order not found")
        payment = get_object_or_404(FakeAcquiringPayment, order=order)
        event = (request.POST.get("event") or "").strip()
        allowed = {x[0] for x in FakeAcquiringPayment.Event.choices}
        if event not in allowed:
            return HttpResponse("Unknown event", status=400)
        _apply_fake_payment_event(order, payment, event)
        payment.refresh_from_db()
        order.refresh_from_db()
        trigger_payload = {
            "showToast": {
                "message": f"Событие: {_payment_event_label(event)}",
                "variant": "success" if payment.status == FakeAcquiringPayment.Status.PAID else "warning",
            }
        }
        if payment.status == FakeAcquiringPayment.Status.PAID:
            trigger_payload["analyticsEvent"] = _order_tracking_payload(order)
        elif event in {FakeAcquiringPayment.Event.FAIL, FakeAcquiringPayment.Event.CANCEL}:
            trigger_payload["analyticsEvent"] = _payment_tracking_payload("payment_failed", order, payment, payment_event=event)
        response = render(
            request,
            "shopfront/partials/fake_payment_panel.html",
            fake_payment_template_context(
                order=order,
                payment=payment,
                order_detail_url=_order_detail_url(order),
                payment_event_url=_fake_payment_event_url(order),
                payment_page_url=_fake_payment_page_url(order),
            ),
        )
        response["HX-Trigger"] = json.dumps(trigger_payload)
        return response
