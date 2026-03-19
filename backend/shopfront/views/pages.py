"""Static and merchandising-facing page views for the shopfront."""

from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.core.paginator import EmptyPage
from django.db.models import Count
from django.middleware.csrf import get_token
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView

from catalog.models import Brand, Category, Collection, Product, normalize_public_media_url
from commerce.models import SellerStore
from core.logging_utils import log_calls
from shopfront.forms import ContactFeedbackForm
from users.models import UserProfile

from ..catalog_selectors import (
    cached_home_category_ids as _cached_home_category_ids,
    cached_home_product_ids as _cached_home_product_ids,
    category_breadcrumbs as _category_breadcrumbs,
    category_descendant_ids as _category_descendant_ids,
    category_slug_path as _category_slug_path,
    ordered_products_with_related as _ordered_products_with_related,
)
from ..models import BrandSubscription
from ..recommendation_service import home_recommendations_context
from ..tasks import notify_contact_feedback

log = logging.getLogger("shopfront")


def _absolute_url(request, path: str) -> str:
    return request.build_absolute_uri(normalize_public_media_url(path))


def _truncate_text(value: str, limit: int = 160) -> str:
    text = (value or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _default_og_image(request) -> str:
    return _absolute_url(request, "/static/shopfront/big_logo.png")


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


def _resolve_category_by_path(raw_path: str) -> Category:
    parts = [part.strip() for part in str(raw_path or "").split("/") if part.strip()]
    if not parts:
        raise Http404("Category not found")
    parent = None
    category = None
    for part in parts:
        category = (
            Category.objects.select_related("parent")
            .filter(parent=parent, slug=part)
            .first()
        )
        if category is None:
            raise Http404("Category not found")
        parent = category
    return category


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
        from ..catalog_selectors import ordered_products_with_related as _ordered_products_with_related

        ctx["products"] = _ordered_products_with_related(product_ids)
        recommendation_ctx = home_recommendations_context(self.request.user, request=self.request, limit=8)
        ctx.update(recommendation_ctx)
        ctx["featured_collections"] = list(Collection.objects.filter(id__in=recommendation_ctx["featured_collection_ids"]))
        ctx["featured_brands"] = list(
            Brand.objects.filter(id__in=recommendation_ctx["featured_brand_ids"])
            .annotate(
                products_count=Count("products", distinct=True),
                categories_count=Count("products__category", distinct=True),
            )
            .order_by("-products_count", "name")
        )
        ctx.update(
            _seo_context(
                self.request,
                title="Servio — маркетплейс товаров для HoReCa",
                description="Servio объединяет поставщиков товаров для ресторанов, кафе, баров, отелей и кейтеринга в одном удобном b2b-каталоге.",
                json_ld=[_website_json_ld(self.request), _organization_json_ld(self.request)],
            )
        )
        return ctx


class _SeoStaticPageView(TemplateView):
    seo_title = ""
    seo_description = ""

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            _seo_context(
                self.request,
                title=self.seo_title,
                description=self.seo_description,
            )
        )
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class AboutPageView(_SeoStaticPageView):
    template_name = "shopfront/about.html"
    seo_title = "О платформе Servio"
    seo_description = "Servio — маркетплейс товаров для HoReCa с понятной логикой закупки, единым каталогом поставщиков и современным b2b-сервисом."


@method_decorator(ensure_csrf_cookie, name="dispatch")
class DeliveryPageView(_SeoStaticPageView):
    template_name = "shopfront/delivery.html"
    seo_title = "Доставка и логистика — Servio"
    seo_description = "Условия доставки заказов Servio: график отгрузок, работа по регионам, документооборот и логистика для HoReCa-команд."


@method_decorator(ensure_csrf_cookie, name="dispatch")
class BuyersPageView(_SeoStaticPageView):
    template_name = "shopfront/buyers.html"
    seo_title = "Для покупателей — Servio"
    seo_description = "Как закупать через Servio: поиск товаров, согласование ассортимента, адреса доставки, повтор заказов и работа с несколькими поставщиками."


@method_decorator(ensure_csrf_cookie, name="dispatch")
class SuppliersPageView(_SeoStaticPageView):
    template_name = "shopfront/suppliers.html"
    seo_title = "Для поставщиков — Servio"
    seo_description = "Servio помогает поставщикам HoReCa продавать через единый маркетплейс: управление ассортиментом, новые клиенты и прозрачный вход в b2b-канал."


@method_decorator(ensure_csrf_cookie, name="dispatch")
class PaymentPageView(_SeoStaticPageView):
    template_name = "shopfront/payment.html"
    seo_title = "Оплата — Servio"
    seo_description = "Форматы оплаты на Servio: безналичный расчет, оплата по счету и прозрачный документооборот для b2b-клиентов."


@method_decorator(ensure_csrf_cookie, name="dispatch")
class ReturnsPageView(_SeoStaticPageView):
    template_name = "shopfront/returns.html"
    seo_title = "Возврат и обмен — Servio"
    seo_description = "Правила возврата и обмена на Servio: приемка товара, фиксация расхождений и порядок обработки претензий для HoReCa-заказов."


@method_decorator(ensure_csrf_cookie, name="dispatch")
class FaqPageView(_SeoStaticPageView):
    template_name = "shopfront/faq.html"
    seo_title = "FAQ — Servio"
    seo_description = "Частые вопросы о работе Servio: регистрация, каталог, доставка, оплата, статусы заказов и работа с поставщиками."


@method_decorator(ensure_csrf_cookie, name="dispatch")
class ContactsPageView(_SeoStaticPageView):
    template_name = "shopfront/contacts.html"
    seo_title = "Контакты Servio"
    seo_description = "Контакты Servio: поддержка клиентов, связь по закупкам, сопровождение поставщиков и рабочие каналы команды платформы."

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
class BrandsPageView(_SeoStaticPageView):
    template_name = "shopfront/brands.html"
    seo_title = "Бренды — Servio"
    seo_description = "Коллекция брендов HoReCa в каталоге Servio: посуда, стекло, бар, сервировка, упаковка и расходные материалы."

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["brands"] = list(
            Brand.objects.annotate(
                products_count=Count("products", distinct=True),
                categories_count=Count("products__category", distinct=True),
                collections_count=Count("products__collections", distinct=True),
            )
            .only("id", "name", "slug", "description", "photo")
            .order_by("-products_count", "name")
        )
        return ctx


class BrandLegacyRedirectView(View):
    @log_calls(log)
    def get(self, request, brand_id: int):
        brand = get_object_or_404(Brand, pk=brand_id)
        return redirect("brand_detail", brand_slug=brand.slug)


class CategoryLegacyRedirectView(View):
    @log_calls(log)
    def get(self, request, category_slug: str):
        category = get_object_or_404(Category.objects.select_related("parent"), slug=category_slug)
        return redirect("category_detail", category_slug=_category_slug_path(category), permanent=True)


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
        product_ids = list(Product.objects.filter(brand=brand).order_by("-is_new", "name").values_list("id", flat=True)[:60])
        ctx["brand"] = brand
        ctx["products"] = _ordered_products_with_related(product_ids, include_rating=True)
        ctx["child_categories"] = list(Category.objects.filter(products__brand=brand).distinct().order_by("name")[:8])
        ctx["featured_collections"] = list(
            Collection.objects.filter(is_active=True, items__product__brand=brand).distinct().order_by("-is_featured", "name")[:4]
        )
        ctx["is_brand_subscribed"] = bool(
            self.request.user.is_authenticated
            and BrandSubscription.objects.filter(user=self.request.user, brand=brand).exists()
        )
        ctx.update(
            _seo_context(
                self.request,
                title=f"{brand.name} — каталог бренда | Servio",
                description=_truncate_text(
                    brand.description or f"Ассортимент бренда {brand.name} в каталоге Servio для профессиональных закупок HoReCa.",
                    160,
                ),
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
        category = _resolve_category_by_path(kwargs["category_slug"])
        category_ids = _category_descendant_ids(category)
        product_ids = list(Product.objects.filter(category_id__in=category_ids).order_by("-is_new", "name").values_list("id", flat=True)[:80])
        ctx["category"] = category
        ctx["products"] = _ordered_products_with_related(product_ids, include_rating=True)
        ctx["breadcrumbs"] = _category_breadcrumbs(category)
        ctx["child_categories"] = list(category.children.order_by("name")[:12])
        ctx["featured_brands"] = list(Brand.objects.filter(products__category_id__in=category_ids).distinct().order_by("name")[:8])
        ctx.update(
            _seo_context(
                self.request,
                title=f"{category.meta_title or category.name} — категория Servio",
                description=_truncate_text(
                    category.meta_description or category.description or category.hero_text or f"Категория {category.name} в каталоге Servio.",
                    160,
                ),
                canonical=_absolute_url(self.request, reverse("category_detail", kwargs={"category_slug": _category_slug_path(category)})),
            )
        )
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CollectionsPageView(_SeoStaticPageView):
    template_name = "shopfront/collections.html"
    seo_title = "Коллекции и подборки — Servio"
    seo_description = "Кураторские коллекции и готовые подборки Servio для сезонных закупок, промо-кампаний и repeat purchase сценариев."

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["collections"] = list(Collection.objects.filter(is_active=True).order_by("-is_featured", "name"))
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
class PromotionsPageView(_SeoStaticPageView):
    template_name = "shopfront/promotions.html"
    seo_title = "Спецпредложения — Servio"
    seo_description = "Подборка акционных и сезонных позиций Servio для ресторанов, кафе, баров, гостиниц и кейтеринга."

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        product_ids = list(Product.objects.filter(is_promo=True).order_by("-is_new", "name").values_list("id", flat=True)[:40])
        ctx["products"] = _ordered_products_with_related(product_ids, include_rating=True)
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class BlogPageView(_SeoStaticPageView):
    template_name = "shopfront/blog.html"
    seo_title = "Журнал Servio"
    seo_description = "Материалы Servio о закупках для HoReCa, управлении ассортиментом, работе с поставщиками и b2b-операциях."

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
        return ctx
