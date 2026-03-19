"""Product detail, seller storefront, and review UI views."""

from __future__ import annotations

import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView
from django.db.models import Prefetch

from catalog.models import Product, ProductImage, ProductReview, ProductReviewComment, ProductReviewVote
from catalog.offer_service import active_offer_queryset, apply_offer_snapshot
from commerce.models import LegalEntityMembership, SellerStore, StoreReview
from core.logging_utils import log_calls
from orders.models import Order, OrderItem

from ..models import BrandSubscription, CategorySubscription, FavoriteProduct
from ..recommendation_service import product_detail_recommendations, product_section_context
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
from . import (
    _absolute_url,
    _cached_home_product_ids,
    _cached_id_list,
    _category_breadcrumbs,
    _compare_ids,
    _default_og_image,
    _ordered_products_with_related,
    _product_json_ld,
    _product_primary_image,
    _product_recommendation_section,
    _record_recently_viewed,
    _recently_viewed_products,
    _seller_rating_summary,
    _seo_context,
    _store_rating_summary,
    _store_reviews_context,
    _tracking_item_from_product,
    _truncate_text,
    log,
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
        product = get_object_or_404(
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
        apply_offer_snapshot([product])
        _record_recently_viewed(self.request, product)
        ctx.update(build_reviews_context(product, self.request.user, seller_rating_summary=_seller_rating_summary))
        seller_store = getattr(getattr(product, "active_offer", None), "seller_store", None) or (
            getattr(product.seller, "seller_store", None) if product.seller_id else None
        )
        seller_summary = _seller_rating_summary(getattr(product, "seller_id", None))
        store_summary = _store_rating_summary(seller_store)
        ctx["seller_store"] = seller_store
        ctx["active_offer"] = getattr(product, "active_offer", None)
        ctx["product_documents"] = list(product.documents.all())
        ctx["product_collections"] = list(product.collections.all()[:6])
        ctx["breadcrumbs"] = _category_breadcrumbs(getattr(product, "category", None))
        ctx["compare_included"] = product.id in _compare_ids(self.request)
        ctx["store_rating_avg"] = store_summary["rating_avg"]
        ctx["store_rating_count"] = store_summary["rating_count"]
        ctx["seller_rating_avg"] = seller_summary["rating_avg"]
        ctx["seller_rating_count"] = seller_summary["rating_count"]
        ctx["is_brand_subscribed"] = bool(
            self.request.user.is_authenticated
            and product.brand_id
            and BrandSubscription.objects.filter(user=self.request.user, brand_id=product.brand_id).exists()
        )
        ctx["is_category_subscribed"] = bool(
            self.request.user.is_authenticated
            and product.category_id
            and CategorySubscription.objects.filter(user=self.request.user, category_id=product.category_id).exists()
        )

        ctx.update(product_detail_recommendations(product, user=self.request.user, request=self.request, limit=12))
        ctx["recently_viewed_products"] = _recently_viewed_products(self.request, exclude_product_id=product.id, limit=8)
        ctx["product_tracking_payload"] = json.dumps(
            {
                "event": "product_view",
                "ecommerce": {
                    "currency": "RUB",
                    "value": float(product.display_price),
                    "items": [_tracking_item_from_product(product)],
                },
            },
            ensure_ascii=False,
        )
        ctx["is_favorite"] = bool(
            self.request.user.is_authenticated
            and FavoriteProduct.objects.filter(user=self.request.user, product=product).exists()
        )
        ctx["can_edit_product"] = bool(
            self.request.user.is_authenticated
            and (
                self.request.user.is_staff
                or self.request.user.is_superuser
                or product.seller_id == self.request.user.id
            )
        )
        primary_image = _product_primary_image(product)
        ctx.update(
            _seo_context(
                self.request,
                title=f"{product.name} — {getattr(product.brand, 'name', 'Servio')} | Servio",
                description=_truncate_text(product.description or f"{product.name} в каталоге Servio: поставки для ресторанов, кафе, баров и гостиничных проектов.", 170),
                canonical=_absolute_url(self.request, f"/product/{product.slug}/"),
                og_type="product",
                og_image=_absolute_url(self.request, primary_image.url) if primary_image else _default_og_image(self.request),
                json_ld=_product_json_ld(self.request, product, seller_store=seller_store),
            )
        )
        return ctx


class ProductRecommendationSectionView(View):
    def get(self, request, *args, **kwargs):
        product = get_object_or_404(
            Product.objects.only("id", "seller_id", "category_id", "brand_id", "name", "slug"),
            slug=kwargs["slug"],
        )
        context = product_section_context(product, kwargs["section"], user=request.user, request=request)
        return render(request, "shopfront/components/recommendation_section.html", context)


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
        store = SellerStore.objects.select_related("owner", "owner__profile", "legal_entity").filter(slug=store_slug).first()
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
        user_model = get_user_model()
        seller_slug = kwargs.get("seller_slug")
        seller_user = user_model.objects.select_related("profile").filter(profile__slug=seller_slug).first()
        if seller_user is None:
            legacy_user = user_model.objects.select_related("profile").filter(username=seller_slug).first()
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
        user_model = get_user_model()
        seller_user = user_model.objects.select_related("profile").filter(username=username).first()
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
        except (TypeError, ValueError):
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
        product = get_object_or_404(Product, pk=pk)
        return redirect(f"/product/{product.slug}/", permanent=True)


class ProductReviewUpsertView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, slug):
        product = get_object_or_404(Product, slug=slug)
        raw_rating = (request.POST.get("rating") or "").strip()
        text = (request.POST.get("text") or "").strip()
        try:
            rating = int(raw_rating)
        except (TypeError, ValueError):
            rating = 0
        if rating < 1 or rating > 5:
            if request.headers.get("HX-Request"):
                return render_reviews_partial(request, product, seller_rating_summary=_seller_rating_summary, status=400)
            messages.error(request, "Рейтинг должен быть от 1 до 5")
            return redirect(f"/product/{product.slug}/#reviews")
        upsert_product_review(product=product, user=request.user, rating=rating, text=text)
        context = build_reviews_context(product, request.user, seller_rating_summary=_seller_rating_summary)
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        messages.success(request, "Отзыв сохранен")
        return redirect(f"/product/{product.slug}/#reviews")


class ProductReviewDeleteView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, slug):
        product = get_object_or_404(Product, slug=slug)
        deleted = delete_product_review(product=product, user=request.user)
        if deleted:
            messages.success(request, "Отзыв удален")
        context = build_reviews_context(product, request.user, seller_rating_summary=_seller_rating_summary)
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"/product/{product.slug}/#reviews")


class ProductReviewCommentCreateView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, slug, review_id):
        product = get_object_or_404(Product, slug=slug)
        review = get_object_or_404(ProductReview, pk=review_id, product=product)
        text = (request.POST.get("text") or "").strip()
        if not text:
            if request.headers.get("HX-Request"):
                return render_reviews_partial(request, product, seller_rating_summary=_seller_rating_summary, status=400)
            return redirect(f"/product/{product.slug}/#reviews")
        create_review_comment(review=review, user=request.user, text=text)
        context = build_reviews_context(product, request.user, seller_rating_summary=_seller_rating_summary)
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"/product/{product.slug}/#reviews")


class ProductReviewCommentUpdateView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, slug, comment_id):
        product = get_object_or_404(Product, slug=slug)
        comment = get_object_or_404(
            ProductReviewComment.objects.select_related("review"),
            pk=comment_id,
            review__product=product,
        )
        if comment.user_id != request.user.id:
            if request.headers.get("HX-Request"):
                return render_reviews_partial(request, product, seller_rating_summary=_seller_rating_summary, status=403)
            return HttpResponse(status=403)
        text = (request.POST.get("text") or "").strip()
        if not text:
            if request.headers.get("HX-Request"):
                return render_reviews_partial(request, product, seller_rating_summary=_seller_rating_summary, status=400)
            return redirect(f"/product/{product.slug}/#reviews")
        update_review_comment(comment=comment, text=text)
        context = build_reviews_context(product, request.user, seller_rating_summary=_seller_rating_summary)
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"/product/{product.slug}/#reviews")


class ProductReviewCommentDeleteView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, slug, comment_id):
        product = get_object_or_404(Product, slug=slug)
        comment = get_object_or_404(
            ProductReviewComment.objects.select_related("review"),
            pk=comment_id,
            review__product=product,
        )
        if comment.user_id != request.user.id:
            if request.headers.get("HX-Request"):
                return render_reviews_partial(request, product, seller_rating_summary=_seller_rating_summary, status=403)
            return HttpResponse(status=403)
        delete_review_comment(comment=comment)
        context = build_reviews_context(product, request.user, seller_rating_summary=_seller_rating_summary)
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"/product/{product.slug}/#reviews")


class ProductReviewVoteView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, slug, review_id):
        product = get_object_or_404(Product, slug=slug)
        review = get_object_or_404(ProductReview, pk=review_id, product=product)
        value = (request.POST.get("value") or "").strip()
        if value not in {ProductReviewVote.Value.HELPFUL, ProductReviewVote.Value.UNHELPFUL}:
            if request.headers.get("HX-Request"):
                return render_reviews_partial(request, product, seller_rating_summary=_seller_rating_summary, status=400)
            return redirect(f"/product/{product.slug}/#reviews")
        apply_review_vote(review=review, user=request.user, value=value)
        context = build_reviews_context(product, request.user, seller_rating_summary=_seller_rating_summary)
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"/product/{product.slug}/#reviews")


class ProductQuestionCreateView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, slug):
        product = get_object_or_404(Product, slug=slug)
        question_text = (request.POST.get("question_text") or "").strip()
        if not question_text:
            if request.headers.get("HX-Request"):
                return render_reviews_partial(request, product, seller_rating_summary=_seller_rating_summary, status=400)
            return redirect(f"/product/{product.slug}/#questions")
        create_product_question(product=product, user=request.user, question_text=question_text)
        context = build_reviews_context(product, request.user, seller_rating_summary=_seller_rating_summary)
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        messages.success(request, "Вопрос отправлен")
        return redirect(f"/product/{product.slug}/#questions")


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
