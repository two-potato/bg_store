from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Prefetch

from catalog.models import Product
from catalog.offer_service import active_offer_queryset, apply_offer_snapshot
from commerce.company_service import resolve_order_approval_requirement
from commerce.models import DeliveryAddress, LegalEntityMembership
from orders.models import Order, OrderApprovalLog, OrderItem


@dataclass(frozen=True)
class CheckoutSubmissionData:
    customer_type: str
    payment_method: str
    delivery_method: str
    pickup_point: str
    delivery_slot: str
    customer_comment: str
    coupon_code: str
    source_channel: str
    guest_email: str


def parse_checkout_submission(request, *, allowed_payment_methods: tuple[str, ...]) -> tuple[CheckoutSubmissionData | None, str | None]:
    """Parse checkout submission."""
    payment_method = request.POST.get("payment_method") or Order.PaymentMethod.CASH
    if payment_method not in allowed_payment_methods:
        return None, "Выбранный способ оплаты недоступен"
    customer_type = request.POST.get("customer_type") or Order.CustomerType.COMPANY
    delivery_method = request.POST.get("delivery_method") or Order.DeliveryMethod.COURIER
    data = CheckoutSubmissionData(
        customer_type=customer_type,
        payment_method=payment_method,
        delivery_method=delivery_method,
        pickup_point=(request.POST.get("pickup_point") or "").strip(),
        delivery_slot=(request.POST.get("delivery_slot") or "").strip(),
        customer_comment=(request.POST.get("customer_comment") or "").strip(),
        coupon_code=(request.POST.get("coupon_code") or "").strip(),
        source_channel=Order.SourceChannel.TWA if request.path.startswith("/twa") else Order.SourceChannel.WEB,
        guest_email=(request.POST.get("customer_email") or "").strip().lower(),
    )
    return data, None


def load_checkout_products(cart: dict) -> dict[int, Product]:
    """Load checkout products."""
    product_ids: list[int] = []
    for raw_id in cart.keys():
        try:
            product_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    products = {
        product.id: product
        for product in Product.objects.select_related("brand", "category", "series", "seller", "seller__seller_store")
        .prefetch_related(Prefetch("seller_offers", queryset=active_offer_queryset()))
        .filter(id__in=product_ids)
    }
    apply_offer_snapshot(products.values())
    return products


def build_checkout_lines(cart: dict, products: dict[int, Product]) -> tuple[list[dict], str | None]:
    """Build checkout lines."""
    checkout_lines: list[dict] = []
    for raw_product_id, item in cart.items():
        try:
            product_id = int(raw_product_id)
        except (TypeError, ValueError):
            continue
        product = products.get(product_id)
        if not product:
            continue
        requested_qty = max(1, int(item.get("qty") or 1))
        if product.display_stock_qty is not None and int(product.display_stock_qty) >= 0 and requested_qty > int(product.display_stock_qty):
            return [], f"Недостаточно на складе для товара: {product.name}"
        checkout_lines.append(
            {
                "product": product,
                "qty": requested_qty,
                "row_total": Decimal(str(product.display_price)) * Decimal(requested_qty),
            }
        )
    return checkout_lines, None


def create_checkout_order(
    *,
    request,
    submission: CheckoutSubmissionData,
    discount_result,
    new_guest_access_token,
) -> tuple[Order | None, str | None]:
    """Create checkout order."""
    if submission.customer_type == Order.CustomerType.COMPANY:
        if not request.user.is_authenticated:
            return None, "Для оформления B2B-заказа войдите в аккаунт компании"
        legal_entity_id = request.POST.get("legal_entity")
        delivery_address_id = request.POST.get("delivery_address")
        if not legal_entity_id:
            return None, "Выберите юр лицо"
        if not LegalEntityMembership.objects.filter(user=request.user, legal_entity_id=legal_entity_id).exists():
            return None, "Нет доступа к выбранному юрлицу"

        resolved_delivery_address_id = None
        if submission.delivery_method == Order.DeliveryMethod.COURIER:
            if not delivery_address_id:
                return None, "Выберите адрес доставки"
            try:
                DeliveryAddress.objects.get(pk=delivery_address_id, legal_entity_id=legal_entity_id)
            except DeliveryAddress.DoesNotExist:
                return None, "Адрес не принадлежит юрлицу"
            resolved_delivery_address_id = delivery_address_id
        elif submission.delivery_method == Order.DeliveryMethod.PICKUP:
            if not submission.pickup_point:
                return None, "Выберите точку самовывоза"
        else:
            return None, "Некорректный способ доставки"

        return (
            Order.objects.create(
                customer_type=Order.CustomerType.COMPANY,
                payment_method=submission.payment_method,
                delivery_method=submission.delivery_method,
                pickup_point=submission.pickup_point if submission.delivery_method == Order.DeliveryMethod.PICKUP else "",
                delivery_slot=submission.delivery_slot,
                legal_entity_id=legal_entity_id,
                delivery_address_id=resolved_delivery_address_id,
                placed_by=request.user,
                requested_by=request.user,
                customer_comment=submission.customer_comment,
                coupon_code=discount_result.coupon.code if discount_result.coupon else "",
                source_channel=submission.source_channel,
            ),
            None,
        )

    fallback_name = (request.user.get_full_name() or request.user.username) if request.user.is_authenticated else ""
    customer_name = (request.POST.get("customer_name") or "").strip() or fallback_name
    customer_email = submission.guest_email
    customer_phone = (request.POST.get("customer_phone") or "").strip()
    address_text = (request.POST.get("address_text") or "").strip()
    if not request.user.is_authenticated and not customer_email:
        return None, "Укажите email для гостевого заказа"
    if not customer_phone:
        return None, "Укажите телефон"
    if submission.delivery_method == Order.DeliveryMethod.COURIER and not address_text:
        return None, "Укажите адрес доставки"
    if submission.delivery_method == Order.DeliveryMethod.PICKUP and not submission.pickup_point:
        return None, "Выберите точку самовывоза"
    if submission.delivery_method not in {Order.DeliveryMethod.COURIER, Order.DeliveryMethod.PICKUP}:
        return None, "Некорректный способ доставки"
    return (
        Order.objects.create(
            customer_type=Order.CustomerType.INDIVIDUAL,
            payment_method=submission.payment_method,
            delivery_method=submission.delivery_method,
            customer_name=customer_name,
            customer_email=customer_email or getattr(request.user, "email", ""),
            customer_phone=customer_phone,
            address_text=address_text if submission.delivery_method == Order.DeliveryMethod.COURIER else "",
            pickup_point=submission.pickup_point if submission.delivery_method == Order.DeliveryMethod.PICKUP else "",
            delivery_slot=submission.delivery_slot,
            placed_by=request.user if request.user.is_authenticated else None,
            guest_access_token=new_guest_access_token() if not request.user.is_authenticated else "",
            customer_comment=submission.customer_comment,
            coupon_code=discount_result.coupon.code if discount_result.coupon else "",
            source_channel=submission.source_channel,
        ),
        None,
    )


def build_order_items(*, cart: dict, products: dict[int, Product], order: Order) -> list[OrderItem]:
    """Build order items."""
    items: list[OrderItem] = []
    for raw_product_id, item in cart.items():
        try:
            product_id = int(raw_product_id)
        except (TypeError, ValueError):
            continue
        product = products.get(product_id)
        if not product:
            continue
        items.append(
            OrderItem(
                order=order,
                product=product,
                seller_offer=getattr(product, "active_offer", None),
                name=product.name,
                price=product.display_price,
                qty=int(item["qty"]) or 1,
            )
        )
    return items


def finalize_checkout_order(*, order: Order, submission: CheckoutSubmissionData, request_user, discount_result) -> None:
    """Handle finalize checkout order."""
    order.recalc_totals(explicit_discount_amount=discount_result.total_discount_amount)
    if submission.customer_type == Order.CustomerType.COMPANY:
        approval = resolve_order_approval_requirement(legal_entity=order.legal_entity, user=request_user, order_total=order.total)
        order.approval_status = Order.ApprovalStatus.PENDING if approval.requires_approval else Order.ApprovalStatus.APPROVED
        approval_comment = approval.reason if approval.requires_approval else "Авто-согласование по политике компании"
    else:
        approval = None
        approval_comment = ""
    order.save(update_fields=["subtotal", "discount_amount", "total", "approval_status"])
    if approval is not None:
        OrderApprovalLog.objects.create(
            order=order,
            actor=request_user,
            decision=OrderApprovalLog.Decision.REQUESTED,
            comment=approval_comment,
        )
