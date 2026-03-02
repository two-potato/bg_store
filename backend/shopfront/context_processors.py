from decimal import Decimal

from catalog.models import Product, Category


def cart_badge(request):
    cart = request.session.get("cart", {}) or {}
    count = 0
    subtotal = Decimal("0.00")

    ids = []
    for raw_pid, payload in cart.items():
        try:
            pid = int(raw_pid)
            qty = max(0, int((payload or {}).get("qty", 0)))
        except Exception:
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
                continue
            price = prices.get(pid)
            if price is None or qty <= 0:
                continue
            subtotal += Decimal(str(price)) * Decimal(qty)

    return {
        "cart_badge_count": count,
        "cart_badge_subtotal": subtotal.quantize(Decimal("0.01")),
    }


def header_categories(request):
    cats = (
        Category.objects.filter(parent__isnull=True)
        .order_by("name")
        .values("id", "name")[:24]
    )
    return {"header_categories": list(cats)}
