"""Product detail, seller storefront, and review UI views."""

from __future__ import annotations


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

from catalog.models import (
    Product,
    ProductReview,
    ProductReviewComment,
    ProductReviewVote,
)
from commerce.models import SellerStore
from core.logging_utils import log_calls

from ..product_detail_service import (
    ProductDetailPageService,
    ProductRecommendationSectionService,
)
from ..store_detail_service import StoreDetailPageService, StoreReviewService
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
from .constants import log
from .utils_catalog import _product_url, _seller_store_for_user
from .utils_seo import _seo_context
from .utils_state import (
    _seller_rating_summary,
    _store_rating_summary,
    _store_reviews_context,
)
from ..catalog_selectors import (
    cached_home_product_ids as _cached_home_product_ids,
    ordered_products_with_related as _ordered_products_with_related,
)


def _storefront_context(store: SellerStore, request_user) -> dict:
    """Build storefront context reused by vendor and store detail pages."""
    product_ids = list(
        Product.objects.filter(seller=store.owner)
        .order_by("-is_new", "name")
        .values_list("id", flat=True)[:60]
    )
    products = _ordered_products_with_related(product_ids, include_rating=True)
    context = {
        "store": store,
        "products": products,
        "store_rating": _store_rating_summary(store),
    }
    context.update(_store_reviews_context(store, request_user))
    return context


@method_decorator(ensure_csrf_cookie, name="dispatch")
class ProductDetailView(TemplateView):
    template_name = "shopfront/product_detail.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Assemble product detail context with reviews, recommendations, and SEO."""
        ctx = super().get_context_data(**kwargs)
        slug = kwargs.get("slug")

        # Use service layer to build complete product detail context
        service = ProductDetailPageService(self.request)
        product_context = service.build_context(slug)

        if product_context is None:
            raise Http404("Product not found")

        # Map dataclass fields back to template context
        ctx.update(
            {
                "product": product_context.product,
                "seller_store": product_context.seller_store,
                "active_offer": product_context.active_offer,
                "product_documents": product_context.product_documents,
                "product_collections": product_context.product_collections,
                "breadcrumbs": product_context.breadcrumbs,
                "compare_included": product_context.compare_included,
                "store_rating_avg": product_context.store_rating_avg,
                "store_rating_count": product_context.store_rating_count,
                "seller_rating_avg": product_context.seller_rating_avg,
                "seller_rating_count": product_context.seller_rating_count,
                "is_brand_subscribed": product_context.is_brand_subscribed,
                "is_category_subscribed": product_context.is_category_subscribed,
                "recently_viewed_products": product_context.recently_viewed_products,
                "product_tracking_payload": product_context.product_tracking_payload,
                "is_favorite": product_context.is_favorite,
                "can_edit_product": product_context.can_edit_product,
                "offer_ladder": product_context.offer_ladder,
                "trust_badges": product_context.trust_badges,
                "product_quality": product_context.product_quality,
            }
        )
        ctx.update(product_context.reviews_context)
        ctx.update(product_context.recommendations)
        ctx.update(product_context.seo_context)

        return ctx


class ProductRecommendationSectionView(View):
    def get(self, request, *args, **kwargs):
        service = ProductRecommendationSectionService(request)
        context = service.build_section_context(
            kwargs.get("slug"), kwargs.get("section")
        )

        if context is None:
            raise Http404("Product not found")

        return render(
            request, "shopfront/components/recommendation_section.html", context
        )


@method_decorator(ensure_csrf_cookie, name="dispatch")
class SellerStoreDetailView(TemplateView):
    template_name = "shopfront/store_detail.html"

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        store_slug = kwargs.get("store_slug")
        store = SellerStore.objects.only("slug").filter(slug=store_slug).first()
        if store is None:
            raise Http404("Store not found")
        return redirect("vendor_detail", vendor_slug=store.slug, permanent=True)

    def get_context_data(self, **kwargs):
        """Render canonical seller store detail page context."""
        ctx = super().get_context_data(**kwargs)
        store_slug = kwargs.get("store_slug")
        store = (
            SellerStore.objects.select_related(
                "owner", "owner__profile", "legal_entity"
            )
            .filter(slug=store_slug)
            .first()
        )
        if store is None:
            raise Http404("Store not found")

        service = StoreDetailPageService(self.request)
        storefront_data = service.build_storefront_context(store)

        ctx.update(
            {
                "store": storefront_data.store,
                "products": storefront_data.products,
                "store_rating": storefront_data.store_rating,
                "trust_metrics": storefront_data.trust_metrics,
            }
        )
        ctx.update(storefront_data.store_reviews)
        ctx.update(service.build_vendor_seo_context(store))

        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class VendorDetailView(TemplateView):
    store = None
    seller_user = None

    @log_calls(log)
    def get(self, request, *args, **kwargs):
        get_token(request)
        vendor_slug = kwargs.get("vendor_slug")
        self.store = (
            SellerStore.objects.select_related(
                "owner", "owner__profile", "legal_entity"
            )
            .filter(slug=vendor_slug)
            .first()
        )
        if self.store is not None:
            return super().get(request, *args, **kwargs)
        user_model = get_user_model()
        self.seller_user = (
            user_model.objects.select_related("profile")
            .filter(profile__slug=vendor_slug)
            .first()
        )
        if self.seller_user is None:
            raise Http404("Vendor not found")
        seller_store = _seller_store_for_user(self.seller_user)
        if (
            seller_store is not None
            and seller_store.slug
            and seller_store.slug != vendor_slug
        ):
            return redirect(
                "vendor_detail", vendor_slug=seller_store.slug, permanent=True
            )
        return super().get(request, *args, **kwargs)

    def get_template_names(self):
        if self.store is not None:
            return ["shopfront/store_detail.html"]
        return ["shopfront/seller_profile.html"]

    def get_context_data(self, **kwargs):
        """Render store or seller profile context under a single vendor URL."""
        ctx = super().get_context_data(**kwargs)
        service = StoreDetailPageService(self.request)

        if self.store is not None:
            store = self.store
            storefront_data = service.build_storefront_context(store)

            ctx.update(
                {
                    "store": storefront_data.store,
                    "products": storefront_data.products,
                    "store_rating": storefront_data.store_rating,
                    "trust_metrics": storefront_data.trust_metrics,
                }
            )
            ctx.update(storefront_data.store_reviews)
            ctx.update(service.build_vendor_seo_context(store))
            return ctx

        seller_user = self.seller_user
        if seller_user is None:
            raise Http404("Vendor not found")

        ctx.update(service.build_seller_profile_context(seller_user))
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
        seller_user = (
            user_model.objects.select_related("profile")
            .filter(profile__slug=seller_slug)
            .first()
        )
        if seller_user is None:
            legacy_user = (
                user_model.objects.select_related("profile")
                .filter(username=seller_slug)
                .first()
            )
            if legacy_user is not None:
                return redirect(
                    "vendor_detail",
                    vendor_slug=getattr(
                        _seller_store_for_user(legacy_user), "slug", None
                    )
                    or legacy_user.profile.slug,
                    permanent=True,
                )
            raise Http404("Seller not found")
        return redirect(
            "vendor_detail",
            vendor_slug=getattr(_seller_store_for_user(seller_user), "slug", None)
            or seller_user.profile.slug,
            permanent=True,
        )

    def get_context_data(self, **kwargs):
        raise Http404("Seller not found")


class SellerStoreLegacyRedirectView(View):
    @log_calls(log)
    def get(self, request, store_id: int):
        store = get_object_or_404(SellerStore, pk=store_id)
        return redirect("vendor_detail", vendor_slug=store.slug, permanent=True)


class SellerProfileLegacyRedirectView(View):
    @log_calls(log)
    def get(self, request, username: str):
        user_model = get_user_model()
        seller_user = (
            user_model.objects.select_related("profile")
            .filter(username=username)
            .first()
        )
        if seller_user is None:
            raise Http404("Seller not found")
        return redirect(
            "vendor_detail",
            vendor_slug=getattr(_seller_store_for_user(seller_user), "slug", None)
            or seller_user.profile.slug,
            permanent=True,
        )


class StoreReviewUpsertView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, store_slug=None, vendor_slug=None):
        store_slug = store_slug or vendor_slug
        store = get_object_or_404(SellerStore, slug=store_slug)
        raw_rating = (request.POST.get("rating") or "").strip()
        text = (request.POST.get("text") or "").strip()
        try:
            rating = int(raw_rating)
        except (TypeError, ValueError):
            rating = 0

        service = StoreReviewService(request)
        result = service.upsert_store_review(store, rating, text)

        if not result.success:
            messages.error(request, result.message)
            return redirect("vendor_detail", vendor_slug=store.slug)

        messages.success(request, result.message)
        return redirect(
            f"{reverse('vendor_detail', kwargs={'vendor_slug': store.slug})}#store-reviews"
        )


class StoreReviewDeleteView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, store_slug=None, vendor_slug=None):
        store_slug = store_slug or vendor_slug
        store = get_object_or_404(SellerStore, slug=store_slug)

        service = StoreReviewService(request)
        result = service.delete_store_review(store)

        if result.deleted:
            messages.success(request, result.message)

        return redirect(
            f"{reverse('vendor_detail', kwargs={'vendor_slug': store.slug})}#store-reviews"
        )


class ProductPkRedirectView(View):
    @log_calls(log)
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        return redirect(_product_url(product), permanent=True)


class ProductSlugRedirectView(View):
    @log_calls(log)
    def get(self, request, slug):
        product = get_object_or_404(Product, slug=slug)
        return redirect(_product_url(product), permanent=True)


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
                return render_reviews_partial(
                    request,
                    product,
                    seller_rating_summary=_seller_rating_summary,
                    status=400,
                )
            messages.error(request, "Рейтинг должен быть от 1 до 5")
            return redirect(f"{_product_url(product)}#reviews")
        upsert_product_review(
            product=product, user=request.user, rating=rating, text=text
        )
        context = build_reviews_context(
            product, request.user, seller_rating_summary=_seller_rating_summary
        )
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        messages.success(request, "Отзыв сохранен")
        return redirect(f"{_product_url(product)}#reviews")


class ProductReviewDeleteView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, slug):
        product = get_object_or_404(Product, slug=slug)
        deleted = delete_product_review(product=product, user=request.user)
        if deleted:
            messages.success(request, "Отзыв удален")
        context = build_reviews_context(
            product, request.user, seller_rating_summary=_seller_rating_summary
        )
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"{_product_url(product)}#reviews")


class ProductReviewCommentCreateView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, slug, review_id):
        product = get_object_or_404(Product, slug=slug)
        review = get_object_or_404(ProductReview, pk=review_id, product=product)
        text = (request.POST.get("text") or "").strip()
        if not text:
            if request.headers.get("HX-Request"):
                return render_reviews_partial(
                    request,
                    product,
                    seller_rating_summary=_seller_rating_summary,
                    status=400,
                )
            return redirect(f"{_product_url(product)}#reviews")
        create_review_comment(review=review, user=request.user, text=text)
        context = build_reviews_context(
            product, request.user, seller_rating_summary=_seller_rating_summary
        )
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"{_product_url(product)}#reviews")


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
                return render_reviews_partial(
                    request,
                    product,
                    seller_rating_summary=_seller_rating_summary,
                    status=403,
                )
            return HttpResponse(status=403)
        text = (request.POST.get("text") or "").strip()
        if not text:
            if request.headers.get("HX-Request"):
                return render_reviews_partial(
                    request,
                    product,
                    seller_rating_summary=_seller_rating_summary,
                    status=400,
                )
            return redirect(f"{_product_url(product)}#reviews")
        update_review_comment(comment=comment, text=text)
        context = build_reviews_context(
            product, request.user, seller_rating_summary=_seller_rating_summary
        )
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"{_product_url(product)}#reviews")


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
                return render_reviews_partial(
                    request,
                    product,
                    seller_rating_summary=_seller_rating_summary,
                    status=403,
                )
            return HttpResponse(status=403)
        delete_review_comment(comment=comment)
        context = build_reviews_context(
            product, request.user, seller_rating_summary=_seller_rating_summary
        )
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"{_product_url(product)}#reviews")


class ProductReviewVoteView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, slug, review_id):
        product = get_object_or_404(Product, slug=slug)
        review = get_object_or_404(ProductReview, pk=review_id, product=product)
        value = (request.POST.get("value") or "").strip()
        if value not in {
            ProductReviewVote.Value.HELPFUL,
            ProductReviewVote.Value.UNHELPFUL,
        }:
            if request.headers.get("HX-Request"):
                return render_reviews_partial(
                    request,
                    product,
                    seller_rating_summary=_seller_rating_summary,
                    status=400,
                )
            return redirect(f"{_product_url(product)}#reviews")
        apply_review_vote(review=review, user=request.user, value=value)
        context = build_reviews_context(
            product, request.user, seller_rating_summary=_seller_rating_summary
        )
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        return redirect(f"{_product_url(product)}#reviews")


class ProductQuestionCreateView(LoginRequiredMixin, View):
    @log_calls(log)
    def post(self, request, slug):
        product = get_object_or_404(Product, slug=slug)
        question_text = (request.POST.get("question_text") or "").strip()
        if not question_text:
            if request.headers.get("HX-Request"):
                return render_reviews_partial(
                    request,
                    product,
                    seller_rating_summary=_seller_rating_summary,
                    status=400,
                )
            return redirect(f"{_product_url(product)}#questions")
        create_product_question(
            product=product, user=request.user, question_text=question_text
        )
        context = build_reviews_context(
            product, request.user, seller_rating_summary=_seller_rating_summary
        )
        if request.headers.get("HX-Request"):
            return render(request, "shopfront/partials/product_reviews.html", context)
        messages.success(request, "Вопрос отправлен")
        return redirect(f"{_product_url(product)}#questions")


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
