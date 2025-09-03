from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from catalog.models import Product, Category, Brand, Tag
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.middleware.csrf import get_token
from django.contrib import messages
from orders.models import Order, OrderItem
from commerce.models import LegalEntityMembership, DeliveryAddress
import logging
from core.logging_utils import log_calls

log = logging.getLogger("shopfront")

def _cart(req):
    return req.session.setdefault("cart", {})

def _cart_summary(req):
    """Build cart items and total for templates."""
    c = _cart(req)
    ids = [int(i) for i in c.keys()]
    prods = {p.id: p for p in Product.objects.filter(id__in=ids)}
    items = []
    total = 0
    for pid, item in c.items():
        p = prods.get(int(pid))
        if not p:
            continue
        qty = max(1, int(item.get("qty", 1)))
        row = float(p.price) * qty
        total += row
        items.append({"p": p, "qty": qty, "row": row})
    return items, total

@ensure_csrf_cookie
@log_calls(log)
def home(request):
    # Ensure CSRF cookie is created for HTMX POSTs from landing
    get_token(request)
    cats = Category.objects.all().order_by("name")[:8]
    products = Product.objects.prefetch_related("images","tags").order_by("-is_new","name")[:12]
    return render(request, "shopfront/home.html", {"cats":cats, "products":products})

@ensure_csrf_cookie
@log_calls(log)
def catalog_page(request):
    get_token(request)
    qs = Product.objects.select_related("brand","series","category").prefetch_related("images","tags").all()
    brand = request.GET.get("brand")
    category = request.GET.get("category")
    q = request.GET.get("q","")
    tag = request.GET.get("tag") or request.GET.get("tag_slug")
    if brand:
        qs = qs.filter(brand_id=brand)
    if category:
        qs = qs.filter(category_id=category)
    if q:
        qs = qs.filter(name__icontains=q)
    if tag:
        # support by id or slug
        if tag.isdigit():
            qs = qs.filter(tags__id=int(tag))
        else:
            qs = qs.filter(tags__slug=tag)
    brands = Brand.objects.all()
    cats = Category.objects.all()
    tags = Tag.objects.all().order_by("name")[:50]
    return render(request, "shopfront/catalog.html", {"products":qs[:60], "brands":brands, "cats":cats, "tags": tags})

@ensure_csrf_cookie
@log_calls(log)
def product_page(request, pk):
    get_token(request)
    p = get_object_or_404(Product.objects.prefetch_related("images","tags"), pk=pk)
    return render(request, "shopfront/product_detail.html", {"p":p})

@log_calls(log)
def cart_badge(request):
    c = _cart(request)
    # Показываем количество позиций, не сумму штук — так информативнее
    count = len(c)
    return render(request, "shopfront/partials/cart_badge.html", {"count":count})

@log_calls(log)
def cart_panel(request):
    items, total = _cart_summary(request)
    return render(request, "shopfront/partials/cart_panel.html", {"items":items, "total":total})

@csrf_exempt
@log_calls(log)
def cart_add(request):
    pid = int(request.POST.get("product_id"))
    qty = int(request.POST.get("qty", 1))
    cart = _cart(request)
    cart[str(pid)] = {"qty": cart.get(str(pid), {"qty":0})["qty"] + qty}
    request.session.modified = True
    log.info("cart_add", extra={"product_id": pid, "qty": qty})
    return render(request, "shopfront/partials/cart_toast.html", status=201)

@csrf_exempt
@log_calls(log)
def cart_remove(request):
    pid = request.POST.get("product_id")
    cart = _cart(request)
    if pid in cart:
        del cart[pid]
    request.session.modified = True
    log.info("cart_remove", extra={"product_id": pid})
    items, total = _cart_summary(request)
    resp = render(request, "shopfront/partials/cart_panel.html", {"items": items, "total": total})
    resp["HX-Trigger"] = '{"showToast": {"message": "Удалено из корзины", "variant": "danger"}}'
    return resp

@csrf_exempt
@log_calls(log)
def cart_clear(request):
    request.session["cart"] = {}
    request.session.modified = True
    log.info("cart_clear")
    items, total = _cart_summary(request)
    resp = render(request, "shopfront/partials/cart_panel.html", {"items": items, "total": total})
    resp["HX-Trigger"] = '{"showToast": {"message": "Корзина очищена", "variant": "danger"}}'
    return resp

@csrf_exempt
@log_calls(log)
def cart_update(request):
    pid = request.POST.get("product_id")
    op = (request.POST.get("op") or "").strip()
    try:
        pid_int = int(pid)
    except Exception:
        return JsonResponse({"ok": False, "error": "invalid_product"}, status=400)
    cart = _cart(request)
    item = cart.get(str(pid_int))
    if not item:
        # Return panel unchanged
        items, total = _cart_summary(request)
        return render(request, "shopfront/partials/cart_panel.html", {"items": items, "total": total}, status=404)
    qty = int(item.get("qty", 1))
    if op == "inc":
        qty += 1
    elif op == "dec":
        qty = max(1, qty - 1)
    elif op == "set":
        try:
            new_q = int(request.POST.get("qty", 1))
            qty = max(1, new_q)
        except Exception:
            pass
    item["qty"] = qty
    cart[str(pid_int)] = item
    request.session.modified = True
    log.info("cart_update", extra={"product_id": pid_int, "op": op, "qty": qty})
    items, total = _cart_summary(request)
    resp = render(request, "shopfront/partials/cart_panel.html", {"items": items, "total": total})
    resp["HX-Trigger"] = '{"showToast": {"message": "Количество обновлено", "variant": "success"}}'
    return resp


@login_required
@log_calls(log)
def checkout_page(request):
    # Build cart summary
    c = _cart(request)
    ids = [int(i) for i in c.keys()]
    prods = {p.id: p for p in Product.objects.filter(id__in=ids)}
    items = []
    total = 0
    for pid, item in c.items():
        p = prods.get(int(pid))
        if not p: continue
        qty = int(item["qty"]) or 1
        row = float(p.price) * qty
        total += row
        items.append({"p": p, "qty": qty, "row": row})
    # Data for company checkout
    memberships = LegalEntityMembership.objects.select_related("legal_entity").filter(user=request.user)
    addresses = DeliveryAddress.objects.filter(legal_entity__members=request.user).order_by("legal_entity__name","-is_default","label")
    return render(request, "shopfront/checkout.html", {
        "items": items,
        "total": total,
        "memberships": memberships,
        "addresses": addresses,
    })


@login_required
@require_http_methods(["POST"])
@log_calls(log)
def checkout_submit(request):
    cust_type = request.POST.get("customer_type") or Order.CustomerType.COMPANY
    pay_method = request.POST.get("payment_method") or Order.PaymentMethod.CASH
    # Build product list from cart
    cart = _cart(request)
    if not cart:
        messages.error(request, "Корзина пуста")
        return redirect("checkout")
    ids = [int(i) for i in cart.keys()]
    products = {p.id: p for p in Product.objects.filter(id__in=ids)}
    if not products:
        messages.error(request, "Товары не найдены")
        return redirect("checkout")
    # Create order depending on type
    if cust_type == Order.CustomerType.COMPANY:
        le_id = request.POST.get("legal_entity")
        addr_id = request.POST.get("delivery_address")
        if not le_id or not addr_id:
            messages.error(request, "Выберите юр лицо и адрес доставки")
            return redirect("checkout")
        # Membership check
        if not LegalEntityMembership.objects.filter(user=request.user, legal_entity_id=le_id).exists():
            messages.error(request, "Нет доступа к выбранному юрлицу")
            return redirect("checkout")
        try:
            DeliveryAddress.objects.get(pk=addr_id, legal_entity_id=le_id)
        except DeliveryAddress.DoesNotExist:
            messages.error(request, "Адрес не принадлежит юрлицу")
            return redirect("checkout")
        order = Order.objects.create(
            customer_type=Order.CustomerType.COMPANY,
            payment_method=pay_method,
            legal_entity_id=le_id,
            delivery_address_id=addr_id,
            placed_by=request.user,
        )
        log.info("order_created_company", extra={"order_id": order.id, "le_id": le_id, "addr_id": addr_id})
    else:
        # Individual path
        name = (request.POST.get("customer_name") or "").strip() or request.user.get_full_name() or request.user.username
        phone = (request.POST.get("customer_phone") or "").strip()
        addr = (request.POST.get("address_text") or "").strip()
        if not phone or not addr:
            messages.error(request, "Укажите телефон и адрес доставки")
            return redirect("checkout")
        order = Order.objects.create(
            customer_type=Order.CustomerType.INDIVIDUAL,
            payment_method=pay_method,
            customer_name=name,
            customer_phone=phone,
            address_text=addr,
            placed_by=request.user,
        )
        log.info("order_created_individual", extra={"order_id": order.id})
    # Create items
    items = []
    for pid, item in cart.items():
        p = products.get(int(pid))
        if not p: continue
        qty = int(item["qty"]) or 1
        items.append(OrderItem(order=order, product=p, name=p.name, price=p.price, qty=qty))
    OrderItem.objects.bulk_create(items)
    order.recalc_totals()
    order.save(update_fields=["subtotal","discount_amount","total"])
    # Clear cart
    request.session["cart"] = {}
    request.session.modified = True
    messages.success(request, f"Заказ #{order.id} оформлен")
    return redirect("account_orders")
