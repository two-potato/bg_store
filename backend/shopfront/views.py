from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from catalog.models import Product, Category, Brand, Tag, ProductReview, ProductReviewComment
from django.core.paginator import Paginator, EmptyPage
from django.views import View
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.csrf import ensure_csrf_cookie
from django.middleware.csrf import get_token
from django.contrib import messages
from django.db.models import Avg, Count, Case, When, IntegerField, Value, FloatField
from django.db.models.functions import Coalesce
from orders.models import Order, OrderItem, FakeAcquiringPayment
from commerce.models import LegalEntityMembership, DeliveryAddress
from .forms import ContactFeedbackForm
from .tasks import notify_contact_feedback
import logging
import json
from uuid import uuid4
from django.utils import timezone
from core.logging_utils import log_calls
from decimal import Decimal
from .search import search_product_ids
from urllib.parse import urlencode

log = logging.getLogger("shopfront")


def _with_rating(qs):
    return qs.annotate(
        rating_avg=Coalesce(Avg("reviews__rating"), Value(0.0), output_field=FloatField()),
        rating_count=Count("reviews", distinct=True),
    )


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

def _cart(req):
    return req.session.setdefault("cart", {})

def _profile_discount_percent(req) -> Decimal:
    if not getattr(req, "user", None) or not req.user.is_authenticated:
        return Decimal("0.00")
    profile = getattr(req.user, "profile", None)
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

def _cart_summary(req):
    """Build cart items and totals for templates."""
    c = _cart(req)
    ids = [int(i) for i in c.keys()]
    prods = {p.id: p for p in Product.objects.filter(id__in=ids)}
    items = []
    subtotal = Decimal("0.00")
    for pid, item in c.items():
        p = prods.get(int(pid))
        if not p:
            continue
        qty = max(1, int(item.get("qty", 1)))
        row = (Decimal(str(p.price)) * Decimal(qty)).quantize(Decimal("0.01"))
        subtotal += row
        items.append({"p": p, "qty": qty, "row": row})
    discount_percent = _profile_discount_percent(req)
    discount_amount = (subtotal * discount_percent / Decimal("100.00")).quantize(Decimal("0.01"))
    total = (subtotal - discount_amount).quantize(Decimal("0.01"))
    return items, subtotal, discount_percent, discount_amount, total

def _checkout_context(req, form_data=None, checkout_error=None):
    items, subtotal, discount_percent, discount_amount, total = _cart_summary(req)
    memberships = LegalEntityMembership.objects.select_related("legal_entity").filter(user=req.user)
    addresses = DeliveryAddress.objects.filter(legal_entity__members=req.user).order_by("legal_entity__name", "-is_default", "label")
    return {
        "items": items,
        "subtotal": subtotal,
        "discount_percent": discount_percent,
        "discount_amount": discount_amount,
        "total": total,
        "memberships": memberships,
        "addresses": addresses,
        "form_data": form_data or {},
        "checkout_error": checkout_error or "",
    }

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
        },
        status=status,
    )


def _cart_badge_context(request):
    c = _cart(request)
    _, subtotal, _, _, _ = _cart_summary(request)
    count = 0
    for payload in c.values():
        try:
            count += max(0, int(payload.get("qty", 0)))
        except Exception:
            continue
    return {"count": count, "subtotal": subtotal}


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
        ctx["cats"] = Category.objects.all().order_by("name")[:8]
        ctx["products"] = _with_rating(
            Product.objects.prefetch_related("images", "tags").order_by("-is_new", "name")
        )[:12]
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class AboutPageView(TemplateView):
    template_name = "shopfront/about.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class DeliveryPageView(TemplateView):
    template_name = "shopfront/delivery.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)


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
class CatalogView(View):
    @log_calls(log)
    def get(self, request):
        get_token(request)
        qs = _with_rating(
            Product.objects.select_related("brand", "series", "category").prefetch_related("images", "tags").all()
        )
        brand = request.GET.get("brand")
        category = request.GET.get("category")
        q = request.GET.get("q","")
        tag = request.GET.get("tag") or request.GET.get("tag_slug")
        sort = (request.GET.get("sort") or "").strip()
        page = int(request.GET.get("page") or 1)
        page_size = 24
        if brand:
            qs = qs.filter(brand_id=brand)
        if category:
            qs = qs.filter(category_id=category)
        es_ranked_ids = []
        if q:
            max_hits = int(getattr(settings, "ES_CATALOG_MAX_HITS", 2000))
            es_ranked_ids = search_product_ids(query=q, limit=max_hits)
            if not es_ranked_ids:
                qs = qs.none()
            else:
                qs = qs.filter(id__in=es_ranked_ids)
        if tag:
            if tag.isdigit():
                qs = qs.filter(tags__id=int(tag))
            else:
                qs = qs.filter(tags__slug=tag)
        sort_map = {
            "new": ["-is_new", "name"],
            "price_asc": ["price", "name"],
            "price_desc": ["-price", "name"],
            "name": ["name"],
            "promo": ["-is_promo", "name"],
            "rating_desc": ["-rating_avg", "-rating_count", "name"],
        }
        if q and es_ranked_ids and not sort:
            rank_order = Case(
                *[When(id=pid, then=pos) for pos, pid in enumerate(es_ranked_ids)],
                default=len(es_ranked_ids),
                output_field=IntegerField(),
            )
            qs = qs.order_by(rank_order)
        else:
            qs = qs.order_by(*sort_map.get(sort, ["-is_new", "name"]))
        paginator = Paginator(qs, page_size)
        try:
            page_obj = paginator.page(page)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages or 1)
        products_page = list(page_obj.object_list)
        base_params = {}
        if q:
            base_params["q"] = q
        if brand:
            base_params["brand"] = brand
        if category:
            base_params["category"] = category
        if tag:
            base_params["tag"] = tag
        if sort:
            base_params["sort"] = sort
        querystring_base = urlencode(base_params)
        category_reset_params = {k: v for k, v in base_params.items() if k != "category"}
        category_reset_querystring = urlencode(category_reset_params)
        category_reset_url = f"/catalog/?{category_reset_querystring}" if category_reset_querystring else "/catalog/"
        if request.headers.get("HX-Request") and request.GET.get("fragment") == "grid_append":
            return render(request, "shopfront/partials/catalog_grid_append.html", {
                "products": products_page,
                "has_next": page_obj.has_next(),
                "next_page": page_obj.next_page_number() if page_obj.has_next() else None,
                "querystring_base": querystring_base,
            })
        brands = Brand.objects.all()
        cats = Category.objects.all()
        tags = Tag.objects.all().order_by("name")[:50]
        sel_brand = brands.filter(id=int(brand)).first() if brand and str(brand).isdigit() else None
        sel_category = cats.filter(id=int(category)).first() if category and str(category).isdigit() else None
        return render(request, "shopfront/catalog.html", {
            "products": products_page,
            "brands": brands,
            "cats": cats,
            "tags": tags,
            "sort": sort or "new",
            "q": q,
            "brand": brand,
            "category": category,
            "tag": tag,
            "has_next": page_obj.has_next(),
            "next_page": page_obj.next_page_number() if page_obj.has_next() else None,
            "querystring_base": querystring_base,
            "total_count": paginator.count,
            "page": page_obj.number,
            "page_size": page_size,
            "sel_brand": sel_brand,
            "sel_category": sel_category,
            "category_reset_url": category_reset_url,
        })


class LiveSearchView(View):
    @log_calls(log)
    def get(self, request):
        q = (request.GET.get("q") or "").strip()
        if len(q) < 3:
            return render(
                request,
                "shopfront/partials/live_search_results.html",
                {"q": q, "products": [], "show": False},
            )

        ids = search_product_ids(query=q, limit=8)
        products = (
            Product.objects.select_related("brand")
            .prefetch_related("images")
            .filter(id__in=ids)
        )
        order = {pid: idx for idx, pid in enumerate(ids)}
        products = sorted(products, key=lambda p: order.get(p.id, 9999))
        return render(
            request,
            "shopfront/partials/live_search_results.html",
            {"q": q, "products": products, "show": True},
        )


def _reviews_context(product: Product, user):
    reviews_qs = (
        product.reviews.select_related("user", "user__profile")
        .prefetch_related("comments__user__profile")
    )
    agg = reviews_qs.aggregate(avg=Avg("rating"), count=Count("id"))
    user_review = None
    if getattr(user, "is_authenticated", False):
        user_review = reviews_qs.filter(user=user).first()
    return {
        "p": product,
        "reviews": reviews_qs[:30],
        "rating_avg": agg["avg"] or 0,
        "rating_count": agg["count"] or 0,
        "user_review": user_review,
    }


def _render_reviews_partial(request, product: Product, status: int = 200):
    return render(
        request,
        "shopfront/partials/product_reviews.html",
        _reviews_context(product, request.user),
        status=status,
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
        pk = kwargs.get("pk")
        p = get_object_or_404(Product.objects.prefetch_related("images", "tags"), pk=pk)
        ctx.update(_reviews_context(p, self.request.user))
        return ctx


class ProductReviewUpsertView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, pk):
        p = get_object_or_404(Product, pk=pk)
        raw_rating = (request.POST.get("rating") or "").strip()
        text = (request.POST.get("text") or "").strip()
        try:
            rating = int(raw_rating)
        except Exception:
            rating = 0
        if rating < 1 or rating > 5:
            if request.headers.get("HX-Request"):
                return _render_reviews_partial(request, p, status=400)
            messages.error(request, "Рейтинг должен быть от 1 до 5")
            return redirect(f"/product/{pk}/#reviews")

        ProductReview.objects.update_or_create(
            product=p,
            user=request.user,
            defaults={"rating": rating, "text": text},
        )
        context = _reviews_context(p, request.user)

        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        messages.success(request, "Отзыв сохранен")
        return redirect(f"/product/{pk}/#reviews")


class ProductReviewDeleteView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, pk):
        p = get_object_or_404(Product, pk=pk)
        deleted, _ = ProductReview.objects.filter(product=p, user=request.user).delete()
        if deleted:
            messages.success(request, "Отзыв удален")
        context = _reviews_context(p, request.user)
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"/product/{pk}/#reviews")


class ProductReviewCommentCreateView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, pk, review_id):
        p = get_object_or_404(Product, pk=pk)
        review = get_object_or_404(ProductReview, pk=review_id, product=p)
        text = (request.POST.get("text") or "").strip()
        if not text:
            if request.headers.get("HX-Request"):
                return _render_reviews_partial(request, p, status=400)
            return redirect(f"/product/{pk}/#reviews")
        ProductReviewComment.objects.create(review=review, user=request.user, text=text)
        context = _reviews_context(p, request.user)
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"/product/{pk}/#reviews")


class ProductReviewCommentUpdateView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, pk, comment_id):
        p = get_object_or_404(Product, pk=pk)
        comment = get_object_or_404(ProductReviewComment.objects.select_related("review"), pk=comment_id, review__product=p)
        if comment.user_id != request.user.id:
            if request.headers.get("HX-Request"):
                return _render_reviews_partial(request, p, status=403)
            return HttpResponse(status=403)
        text = (request.POST.get("text") or "").strip()
        if not text:
            if request.headers.get("HX-Request"):
                return _render_reviews_partial(request, p, status=400)
            return redirect(f"/product/{pk}/#reviews")
        comment.text = text
        comment.save(update_fields=["text", "updated_at"])
        context = _reviews_context(p, request.user)
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"/product/{pk}/#reviews")


class ProductReviewCommentDeleteView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, pk, comment_id):
        p = get_object_or_404(Product, pk=pk)
        comment = get_object_or_404(ProductReviewComment.objects.select_related("review"), pk=comment_id, review__product=p)
        if comment.user_id != request.user.id:
            if request.headers.get("HX-Request"):
                return _render_reviews_partial(request, p, status=403)
            return HttpResponse(status=403)
        comment.delete()
        context = _reviews_context(p, request.user)
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"/product/{pk}/#reviews")

@method_decorator(ensure_csrf_cookie, name="dispatch")
class TwaHomeView(TemplateView):
    template_name = "shopfront/twa_home.html"
    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["products"] = _with_rating(
            Product.objects.prefetch_related("images", "tags").order_by("-is_new", "name")
        )[:12]
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
        items, subtotal, discount_percent, discount_amount, total = _cart_summary(request)
        return render(
            request,
            self.template_name,
            {
                "items": items,
                "subtotal": subtotal,
                "discount_percent": discount_percent,
                "discount_amount": discount_amount,
                "total": total,
            },
        )

class CartAddView(View):
    @log_calls(log)
    def post(self, request):
        pid = int(request.POST.get("product_id"))
        qty = int(request.POST.get("qty", 1))
        cart = _cart(request)
        try:
            p = Product.objects.get(pk=pid)
            max_qty = max(0, int(p.stock_qty or 0))
        except Product.DoesNotExist:
            log.warning("cart_add_product_not_found", extra={"product_id": pid})
            return JsonResponse({"ok": False, "error": "product_not_found"}, status=404)
        current = int(cart.get(str(pid), {"qty": 0}).get("qty", 0))
        new_qty = current + max(1, qty)
        if max_qty > 0 and new_qty > max_qty:
            log.info("cart_qty_capped_by_stock", extra={"product_id": pid, "requested": new_qty, "stock": max_qty})
            new_qty = max_qty
        if new_qty <= 0:
            cart.pop(str(pid), None)
        else:
            cart[str(pid)] = {"qty": new_qty}
        request.session.modified = True
        log.info("cart_add", extra={"product_id": pid, "qty": qty})
        current_qty = cart.get(str(pid), {}).get("qty", 0)
        triggers = json.dumps({
            "showToast": {"message": "Товар добавлен в корзину", "variant": "success"},
            "cartChanged": {},
            "cartQtyUpdated": {"product_id": pid, "qty": current_qty},
        })
        resp = HttpResponse("", status=200)
        resp["HX-Trigger"] = triggers
        resp["HX-Trigger-After-Settle"] = triggers
        return _attach_cart_badge_oob(request, resp)

class CartPageView(TemplateView):
    template_name = "shopfront/cart.html"
    @log_calls(log)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        items, subtotal, discount_percent, discount_amount, total = _cart_summary(self.request)
        ctx.update(
            {
                "items": items,
                "subtotal": subtotal,
                "discount_percent": discount_percent,
                "discount_amount": discount_amount,
                "total": total,
            }
        )
        return ctx

class CartRemoveView(View):
    @log_calls(log)
    def post(self, request):
        pid = request.POST.get("product_id")
        cart = _cart(request)
        if pid in cart:
            del cart[pid]
        request.session.modified = True
        log.info("cart_remove", extra={"product_id": pid})
        items, subtotal, discount_percent, discount_amount, total = _cart_summary(request)
        resp = _render_cart_fragment(request, items, subtotal, discount_percent, discount_amount, total)
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
        request.session["cart"] = {}
        request.session.modified = True
        log.info("cart_clear")
        items, subtotal, discount_percent, discount_amount, total = _cart_summary(request)
        resp = _render_cart_fragment(request, items, subtotal, discount_percent, discount_amount, total)
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
        cart = _cart(request)
        item = cart.get(str(pid_int))
        if not item:
            items, subtotal, discount_percent, discount_amount, total = _cart_summary(request)
            return _render_cart_fragment(request, items, subtotal, discount_percent, discount_amount, total, status=404)
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
        try:
            p = Product.objects.get(pk=pid_int)
            max_qty = max(0, int(p.stock_qty or 0))
        except Product.DoesNotExist:
            log.warning("cart_update_product_not_found", extra={"product_id": pid_int})
            max_qty = 0
        if max_qty > 0 and qty > max_qty:
            log.info("cart_qty_capped_by_stock", extra={"product_id": pid_int, "requested": qty, "stock": max_qty})
            qty = max_qty
        if qty <= 0:
            cart.pop(str(pid_int), None)
            qty = 0
        else:
            item["qty"] = qty
            cart[str(pid_int)] = item
        request.session.modified = True
        log.info("cart_update", extra={"product_id": pid_int, "op": op, "qty": qty})
        items, subtotal, discount_percent, discount_amount, total = _cart_summary(request)
        resp = _render_cart_fragment(request, items, subtotal, discount_percent, discount_amount, total)
        resp["HX-Trigger"] = json.dumps({
            "showToast": {"message": "Количество обновлено", "variant": "success"},
            "cartChanged": {},
            "cartQtyUpdated": {"product_id": pid_int, "qty": qty},
        })
        return _attach_cart_badge_oob(request, resp)


class CheckoutPageView(LoginRequiredMixin, TemplateView):
    template_name = "shopfront/checkout.html"
    @log_calls(log)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_checkout_context(self.request))
        return ctx


class CheckoutSubmitView(LoginRequiredMixin, View):
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
        if idem_key:
            key_obj, created = IdempotencyKey.create_or_get(user_id=request.user.id, route="checkout_submit", key=idem_key, ttl_sec=600)
            if not created:
                log.info("checkout_idempotent_reused", extra={"user_id": request.user.id, "key": idem_key})
                if is_hx:
                    return fail("Заказ уже оформлен")
                messages.info(request, "Заказ уже оформлен")
                return redirect("account_orders")
        cust_type = request.POST.get("customer_type") or Order.CustomerType.COMPANY
        pay_method = request.POST.get("payment_method") or Order.PaymentMethod.CASH
        # Build product list from cart
        cart = _cart(request)
        if not cart:
            return fail("Корзина пуста")
        ids = [int(i) for i in cart.keys()]
        products = {p.id: p for p in Product.objects.filter(id__in=ids)}
        if not products:
            return fail("Товары не найдены")
        # Stock validation
        for pid, item in cart.items():
            p = products.get(int(pid))
            if not p:
                continue
            req_qty = max(1, int(item.get("qty") or 1))
            if p.stock_qty is not None and int(p.stock_qty) >= 0 and req_qty > int(p.stock_qty):
                log.info("checkout_stock_insufficient", extra={"product_id": p.id, "name": p.name, "requested": req_qty, "stock": int(p.stock_qty)})
                return fail(f"Недостаточно на складе для товара: {p.name}")
        # Create order depending on type
        if cust_type == Order.CustomerType.COMPANY:
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
            )
            log.info("order_created_company", extra={"order_id": order.id, "le_id": le_id, "addr_id": addr_id})
        else:
            name = (request.POST.get("customer_name") or "").strip() or request.user.get_full_name() or request.user.username
            phone = (request.POST.get("customer_phone") or "").strip()
            addr = (request.POST.get("address_text") or "").strip()
            if not phone or not addr:
                return fail("Укажите телефон и адрес доставки")
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
            if not p:
                continue
            qty = int(item["qty"]) or 1
            items.append(OrderItem(order=order, product=p, name=p.name, price=p.price, qty=qty))
        OrderItem.objects.bulk_create(items)
        order.recalc_totals()
        order.save(update_fields=["subtotal","discount_amount","total"])
        request.session["cart"] = {}
        request.session.modified = True
        if pay_method == Order.PaymentMethod.MIR_CARD:
            payment, _ = FakeAcquiringPayment.objects.get_or_create(
                order=order,
                defaults={
                    "amount": order.total,
                    "provider_payment_id": f"fake_{order.id}_{uuid4().hex[:10]}",
                },
            )
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
                    {"order": order, "payment": payment},
                )
                resp["HX-Trigger"] = json.dumps(
                    {
                        "showToast": {"message": f"Заказ #{order.id} создан. Запущен тест эквайринга", "variant": "success"},
                        "cartChanged": {},
                    }
                )
                return resp
            messages.info(request, f"Заказ #{order.id} создан. Откройте симулятор оплаты.")
            return redirect("fake_payment_page", order_id=order.id)
        if is_hx:
            resp = render(request, "shopfront/partials/checkout_success_panel.html", {"order": order})
            resp["HX-Trigger"] = json.dumps({
                "showToast": {"message": f"Заказ #{order.id} оформлен", "variant": "success"},
                "cartChanged": {},
            })
            return resp
        messages.success(request, f"Заказ #{order.id} оформлен")
        return redirect("account_orders")


class FakePaymentPageView(LoginRequiredMixin, TemplateView):
    template_name = "shopfront/fake_payment.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        order = get_object_or_404(Order.objects.select_related("placed_by"), pk=kwargs["order_id"], placed_by=request.user)
        payment = get_object_or_404(FakeAcquiringPayment, order=order)
        return render(request, self.template_name, {"order": order, "payment": payment})


class FakePaymentEventView(LoginRequiredMixin, View):
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
        response = render(request, "shopfront/partials/fake_payment_panel.html", {"order": order, "payment": payment})
        response["HX-Trigger"] = json.dumps(
            {
                "showToast": {
                    "message": f"Событие: {_payment_event_label(event)}",
                    "variant": "success" if payment.status == FakeAcquiringPayment.Status.PAID else "warning",
                }
            }
        )
        return response
