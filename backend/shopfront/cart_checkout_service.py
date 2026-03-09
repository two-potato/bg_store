import json
import logging
from collections import OrderedDict
from decimal import Decimal

from django.db.models import Prefetch

from catalog.models import Product, ProductImage
from catalog.offer_service import active_offer_queryset, apply_offer_snapshot
from commerce.company_service import ensure_approval_policy, ensure_company_workspace
from commerce.models import CompanyMembership, DeliveryAddress
from orders.models import Order
from promotions.services import resolve_checkout_discount

log = logging.getLogger("shopfront")


def session_cart(request):
    return request.session.setdefault("cart", {})


def profile_discount_percent(request) -> Decimal:
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return Decimal("0.00")
    profile = getattr(request.user, "profile", None)
    raw = getattr(profile, "discount", Decimal("0.00")) if profile else Decimal("0.00")
    try:
        pct = Decimal(str(raw))
    except Exception:
        pct = Decimal("0.00")
    if pct < 0:
        return Decimal("0.00")
    if pct > 100:
        return Decimal("100.00")
    return pct


def cart_summary(request):
    cart = session_cart(request)
    product_ids: list[int] = []
    for raw_id in cart.keys():
        try:
            product_ids.append(int(raw_id))
        except Exception:
            continue
    products = {
        product.id: product
        for product in Product.objects.select_related("brand", "category", "series", "seller", "seller__seller_store")
        .prefetch_related(
            Prefetch(
                "images",
                queryset=ProductImage.objects.only("id", "product_id", "url", "alt", "ordering").order_by("ordering", "id"),
                to_attr="prefetched_images",
            ),
            Prefetch("seller_offers", queryset=active_offer_queryset()),
        )
        .filter(id__in=product_ids)
    }
    apply_offer_snapshot(products.values())
    items = []
    seller_groups: OrderedDict[str, dict] = OrderedDict()
    subtotal = Decimal("0.00")
    cart_count = 0
    line_items = []
    for product_id, payload in cart.items():
        try:
            product_id_int = int(product_id)
        except Exception:
            continue
        product = products.get(product_id_int)
        if not product:
            continue
        qty = max(1, int(payload.get("qty", 1)))
        price = Decimal(str(product.display_price))
        row_total = (price * Decimal(qty)).quantize(Decimal("0.01"))
        subtotal += row_total
        cart_count += qty
        seller_store = getattr(getattr(product, "active_offer", None), "seller_store", None) or (
            getattr(product.seller, "seller_store", None) if product.seller_id else None
        )
        seller_key = f"seller:{getattr(seller_store, 'id', 0) or 0}:{getattr(product.seller, 'id', 0) or 0}"
        if seller_key not in seller_groups:
            seller_groups[seller_key] = {
                "title": getattr(seller_store, "name", "") or getattr(product.seller, "username", "") or "Servio",
                "slug": getattr(seller_store, "slug", "") or "",
                "items": [],
                "subtotal": Decimal("0.00"),
            }
        item_payload = {"p": product, "qty": qty, "row": row_total, "seller_store": seller_store}
        seller_groups[seller_key]["items"].append(item_payload)
        seller_groups[seller_key]["subtotal"] += row_total
        items.append(item_payload)
        line_items.append({"product": product, "qty": qty, "row_total": row_total})

    coupon_code = ""
    if request.method == "POST":
        coupon_code = (request.POST.get("coupon_code") or "").strip()
    elif request.method == "GET":
        coupon_code = (request.GET.get("coupon_code") or "").strip()
    guest_email = (request.POST.get("customer_email") or "").strip().lower() if request.method == "POST" else ""
    customer_type = (
        request.POST.get("customer_type") or Order.CustomerType.INDIVIDUAL
    ) if request.method == "POST" else Order.CustomerType.INDIVIDUAL
    discount_result = resolve_checkout_discount(
        user=request.user,
        customer_type=customer_type,
        coupon_code=coupon_code,
        guest_email=guest_email,
        lines=line_items,
        lock=False,
    )
    discount_amount = discount_result.total_discount_amount
    discount_percent = profile_discount_percent(request)
    total = (subtotal - discount_amount).quantize(Decimal("0.01"))
    return {
        "items": items,
        "subtotal": subtotal,
        "discount_percent": discount_percent,
        "discount_amount": discount_amount,
        "total": total,
        "seller_groups": list(seller_groups.values()),
        "seller_count": len(seller_groups),
        "cart_count": cart_count,
        "coupon_discount_amount": discount_result.coupon_discount_amount,
        "profile_discount_amount": discount_result.profile_discount_amount,
        "coupon_validation_error": discount_result.error,
        "resolved_coupon_code": discount_result.coupon.code if discount_result.coupon else "",
    }


def cart_badge_context(request):
    cart = session_cart(request)
    cart_ctx = cart_summary(request)
    count = 0
    for payload in cart.values():
        try:
            count += max(0, int(payload.get("qty", 0)))
        except Exception:
            continue
    return {"count": count, "subtotal": cart_ctx["subtotal"]}


def checkout_company_snapshots(request, memberships):
    snapshots = []
    for membership in memberships:
        company = ensure_company_workspace(membership.legal_entity)
        policy = ensure_approval_policy(company)
        company_membership = CompanyMembership.objects.filter(company=company, user=request.user).first()
        snapshots.append(
            {
                "legal_entity_id": membership.legal_entity_id,
                "company": company,
                "policy": policy,
                "company_membership": company_membership,
            }
        )
    return snapshots


def checkout_identity_defaults(request):
    if not request.user.is_authenticated:
        return "", ""
    return request.user.get_full_name() or request.user.username or "", getattr(request.user, "email", "") or ""


def checkout_addresses_queryset(request):
    if not request.user.is_authenticated:
        return DeliveryAddress.objects.none()
    return DeliveryAddress.objects.filter(legal_entity__members=request.user).order_by("legal_entity__name", "-is_default", "label")


def checkout_cart_tracking_payload(cart_ctx, tracking_item_from_product) -> str:
    if not cart_ctx["items"]:
        return "{}"
    return json.dumps(
        {
            "currency": "RUB",
            "value": float(cart_ctx["total"]),
            "seller_count": cart_ctx["seller_count"],
            "items": [tracking_item_from_product(item["p"], quantity=item["qty"]) for item in cart_ctx["items"]],
        },
        ensure_ascii=False,
    )
