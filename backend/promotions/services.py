from dataclasses import dataclass
from decimal import Decimal

from django.contrib.auth.models import AnonymousUser
from django.db.models import Count
from django.utils import timezone

from orders.models import Order

from .models import Coupon, PromotionRedemption


@dataclass
class CheckoutDiscountResult:
    subtotal: Decimal
    profile_discount_amount: Decimal
    coupon_discount_amount: Decimal
    total_discount_amount: Decimal
    coupon: Coupon | None = None
    error: str = ""


def _quantize(value: Decimal) -> Decimal:
    return Decimal(str(value or "0.00")).quantize(Decimal("0.01"))


def _profile_discount_amount(user, subtotal: Decimal) -> Decimal:
    if not user or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
        return Decimal("0.00")
    profile = getattr(user, "profile", None)
    raw = getattr(profile, "discount", Decimal("0.00")) if profile else Decimal("0.00")
    try:
        pct = Decimal(str(raw))
    except Exception:
        pct = Decimal("0.00")
    pct = min(max(pct, Decimal("0.00")), Decimal("100.00"))
    return _quantize(subtotal * pct / Decimal("100.00"))


def _eligible_row_total(rule, line: dict) -> Decimal:
    product = line["product"]
    row_total = _quantize(line["row_total"])
    if rule.product_id and product.id != rule.product_id:
        return Decimal("0.00")
    if rule.category_id and getattr(product, "category_id", None) != rule.category_id:
        return Decimal("0.00")
    if rule.brand_id and getattr(product, "brand_id", None) != rule.brand_id:
        return Decimal("0.00")
    if rule.seller_id and getattr(product, "seller_id", None) != rule.seller_id:
        return Decimal("0.00")
    return row_total


def _coupon_is_allowed_for_subject(rule, *, user, customer_type: str) -> bool:
    scope = rule.customer_scope
    is_auth = bool(user and getattr(user, "is_authenticated", False))
    if scope == rule.CustomerScope.ALL:
        return True
    if scope == rule.CustomerScope.AUTHENTICATED:
        return is_auth
    if scope == rule.CustomerScope.GUEST:
        return not is_auth
    if scope == rule.CustomerScope.COMPANY:
        return customer_type == Order.CustomerType.COMPANY
    if scope == rule.CustomerScope.INDIVIDUAL:
        return customer_type == Order.CustomerType.INDIVIDUAL
    return False


def resolve_checkout_discount(
    *,
    user,
    customer_type: str,
    coupon_code: str,
    guest_email: str,
    lines: list[dict],
    lock: bool = False,
) -> CheckoutDiscountResult:
    subtotal = _quantize(sum((line["row_total"] for line in lines), start=Decimal("0.00")))
    profile_discount_amount = _profile_discount_amount(user, subtotal)
    normalized_code = (coupon_code or "").strip().upper()

    if not normalized_code:
        return CheckoutDiscountResult(
            subtotal=subtotal,
            profile_discount_amount=profile_discount_amount,
            coupon_discount_amount=Decimal("0.00"),
            total_discount_amount=profile_discount_amount,
        )

    now = timezone.now()
    query = Coupon.objects.select_related("rule")
    if lock:
        query = query.select_for_update()
    try:
        coupon = query.get(code=normalized_code)
    except Coupon.DoesNotExist:
        return CheckoutDiscountResult(subtotal, profile_discount_amount, Decimal("0.00"), profile_discount_amount, error="Промокод не найден")

    rule = coupon.rule
    if not coupon.is_active or not rule.is_live(now=now):
        return CheckoutDiscountResult(subtotal, profile_discount_amount, Decimal("0.00"), profile_discount_amount, coupon=coupon, error="Промокод неактивен")
    if subtotal < _quantize(rule.min_subtotal):
        return CheckoutDiscountResult(subtotal, profile_discount_amount, Decimal("0.00"), profile_discount_amount, coupon=coupon, error=f"Промокод доступен от суммы {rule.min_subtotal} ₽")
    if not _coupon_is_allowed_for_subject(rule, user=user, customer_type=customer_type):
        return CheckoutDiscountResult(subtotal, profile_discount_amount, Decimal("0.00"), profile_discount_amount, coupon=coupon, error="Промокод недоступен для этого типа заказа")

    eligible_subtotal = _quantize(sum((_eligible_row_total(rule, line) for line in lines), start=Decimal("0.00")))
    if eligible_subtotal <= 0:
        return CheckoutDiscountResult(subtotal, profile_discount_amount, Decimal("0.00"), profile_discount_amount, coupon=coupon, error="Промокод не подходит к товарам в корзине")

    usage_stats = coupon.redemptions.aggregate(total=Count("id"))
    total_redemptions = int(usage_stats.get("total") or 0)
    if coupon.usage_limit is not None and total_redemptions >= coupon.usage_limit:
        return CheckoutDiscountResult(subtotal, profile_discount_amount, Decimal("0.00"), profile_discount_amount, coupon=coupon, error="Промокод исчерпан")

    redemption_qs = coupon.redemptions.all()
    if user and getattr(user, "is_authenticated", False):
        redemption_qs = redemption_qs.filter(redeemed_by=user)
    elif guest_email:
        redemption_qs = redemption_qs.filter(guest_email__iexact=guest_email.strip())
    else:
        redemption_qs = redemption_qs.none()
    if coupon.per_user_limit is not None and redemption_qs.count() >= coupon.per_user_limit:
        return CheckoutDiscountResult(subtotal, profile_discount_amount, Decimal("0.00"), profile_discount_amount, coupon=coupon, error="Лимит использования промокода исчерпан")

    if rule.discount_type == rule.DiscountType.FIXED:
        coupon_discount_amount = min(_quantize(rule.discount_value), eligible_subtotal)
    else:
        coupon_discount_amount = _quantize(eligible_subtotal * _quantize(rule.discount_value) / Decimal("100.00"))
        coupon_discount_amount = min(coupon_discount_amount, eligible_subtotal)

    if rule.stack_with_profile_discount:
        total_discount_amount = min(subtotal, _quantize(profile_discount_amount + coupon_discount_amount))
    else:
        total_discount_amount = max(profile_discount_amount, coupon_discount_amount)

    return CheckoutDiscountResult(
        subtotal=subtotal,
        profile_discount_amount=profile_discount_amount,
        coupon_discount_amount=coupon_discount_amount,
        total_discount_amount=_quantize(total_discount_amount),
        coupon=coupon,
    )


def create_redemption(*, order, discount_result: CheckoutDiscountResult, user, guest_email: str = ""):
    if not discount_result.coupon or discount_result.coupon_discount_amount <= 0:
        return None
    return PromotionRedemption.objects.create(
        coupon=discount_result.coupon,
        order=order,
        redeemed_by=user if user and getattr(user, "is_authenticated", False) else None,
        guest_email=(guest_email or "").strip().lower(),
        discount_amount=discount_result.coupon_discount_amount,
    )
