"""Service layer for store detail pages and seller profile context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.db.models import Count

from catalog.models import Product
from catalog.models import ProductQuestion
from commerce.models import LegalEntityMembership, SellerStore
from orders.models import Order, OrderClaim, OrderItem, SellerOrder

from .catalog_selectors import (
    ordered_products_with_related as _ordered_products_with_related,
)
from .views.utils_catalog import _vendor_url
from .views.utils_seo import _absolute_url, _seo_context
from .views.utils_state import (
    _seller_rating_summary,
    _store_rating_summary,
    _store_reviews_context,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser, User
    from django.http import HttpRequest


@dataclass(slots=True)
class StorefrontContextData:
    """Assembled context for store/vendor detail page."""

    store: SellerStore
    products: list[Product]
    store_rating: dict[str, Any]
    store_reviews: dict[str, Any]
    trust_metrics: list[dict[str, Any]]


@dataclass(slots=True)
class StoreReviewOperationResult:
    """Result of store review operation."""

    success: bool
    message: str
    deleted: bool = False


class StoreDetailPageService:
    """Assemble store detail page context for storefront and vendor URLs."""

    def __init__(self, request: HttpRequest) -> None:
        self.request = request
        self.user: User | AnonymousUser = request.user

    def build_storefront_context(self, store: SellerStore) -> StorefrontContextData:
        """Build context for store detail page (reused by multiple views)."""
        product_ids = list(
            Product.objects.filter(seller=store.owner)
            .order_by("-is_new", "name")
            .values_list("id", flat=True)[:60]
        )
        products = _ordered_products_with_related(product_ids, include_rating=True)
        store_rating = _store_rating_summary(store)
        store_reviews_context = _store_reviews_context(store, self.user)
        seller_orders = SellerOrder.objects.filter(seller=store.owner)
        total_orders = seller_orders.count()
        delivered_orders = seller_orders.filter(status=SellerOrder.Status.DELIVERED).count()
        canceled_orders = seller_orders.filter(status=SellerOrder.Status.CANCELED).count()
        claims_count = OrderClaim.objects.filter(order__seller_orders__seller=store.owner).distinct().count()
        answered_questions = list(
            ProductQuestion.objects.filter(product__seller=store.owner, answered_at__isnull=False).only("created_at", "answered_at")[:40]
        )
        avg_response_hours = 0
        if answered_questions:
            total_seconds = sum(
                max(0.0, (question.answered_at - question.created_at).total_seconds())
                for question in answered_questions
                if question.answered_at and question.created_at
            )
            avg_response_hours = round(total_seconds / max(1, len(answered_questions)) / 3600, 1)
        top_categories = list(
            Product.objects.filter(seller=store.owner, category__isnull=False)
            .values("category__name")
            .annotate(total=Count("id"))
            .order_by("-total", "category__name")[:3]
        )
        docs_ready = Product.objects.filter(seller=store.owner, documents__isnull=False).distinct().count()
        products_total = max(1, Product.objects.filter(seller=store.owner).count())
        trust_metrics = [
            {
                "label": "On-time shipment",
                "value": f"{round((delivered_orders / max(1, total_orders)) * 100)}%",
                "detail": f"{delivered_orders} из {total_orders} seller orders доведены до delivered",
            },
            {
                "label": "Response time",
                "value": f"{avg_response_hours or 24} ч",
                "detail": "Среднее время ответа на вопросы по товарам",
            },
            {
                "label": "Claim rate",
                "value": f"{round((claims_count / max(1, total_orders)) * 100)}%",
                "detail": "Доля заказов со спором или претензией",
            },
            {
                "label": "Cancellation rate",
                "value": f"{round((canceled_orders / max(1, total_orders)) * 100)}%",
                "detail": "Отмены относительно всех seller orders",
            },
            {
                "label": "Verification",
                "value": "Подтверждено" if store.moderation_status == store.ModerationStatus.APPROVED else "На проверке",
                "detail": f"Карточки с документами: {docs_ready} из {products_total}",
            },
            {
                "label": "Top categories",
                "value": ", ".join(row["category__name"] for row in top_categories) or "Ассортимент расширяется",
                "detail": "Ключевые категории магазина на текущий момент",
            },
        ]

        return StorefrontContextData(
            store=store,
            products=products,
            store_rating=store_rating,
            store_reviews=store_reviews_context,
            trust_metrics=trust_metrics,
        )

    def build_vendor_seo_context(self, store: SellerStore) -> dict[str, Any]:
        """Build SEO context for vendor store page."""
        return _seo_context(
            self.request,
            title=f"{store.name} — витрина поставщика | Servio",
            description=f"Ассортимент магазина {store.name} на Servio: поставщик товаров для HoReCa, актуальные позиции и профессиональный каталог.",
            canonical=_absolute_url(self.request, _vendor_url(store=store)),
        )

    def build_seller_profile_context(self, seller_user: User) -> dict[str, Any]:
        """Build context for seller profile page (user without SellerStore)."""
        memberships = LegalEntityMembership.objects.select_related(
            "legal_entity", "role"
        ).filter(user=seller_user)
        stores = (
            SellerStore.objects.select_related("legal_entity")
            .filter(owner=seller_user)
            .order_by("name")
        )
        seller_rating = _seller_rating_summary(seller_user.id)

        display_name = seller_user.profile.full_name or seller_user.username

        context = {
            "seller_user": seller_user,
            "seller_profile": seller_user.profile,
            "memberships": memberships,
            "stores": stores,
            "seller_rating": seller_rating,
        }

        seo_context = _seo_context(
            self.request,
            title=f"{display_name} — профиль поставщика | Servio",
            description=f"Профиль поставщика {display_name} на Servio: магазины, юридические данные и ассортимент для HoReCa.",
            canonical=_absolute_url(self.request, _vendor_url(user=seller_user)),
        )

        context.update(seo_context)
        return context


class StoreReviewService:
    """Manage store review creation and deletion."""

    def __init__(self, request: HttpRequest) -> None:
        self.request = request
        self.user: User = request.user

    def upsert_store_review(
        self, store: SellerStore, rating: int, text: str = ""
    ) -> StoreReviewOperationResult:
        """Create or update store review for current user."""
        if rating < 1 or rating > 5:
            return StoreReviewOperationResult(
                success=False,
                message="Рейтинг магазина должен быть от 1 до 5",
            )

        # Check if user has verified purchase
        has_verified_purchase = OrderItem.objects.filter(
            order__placed_by=self.user,
            order__status__in=[
                Order.Status.CONFIRMED,
                Order.Status.PAID,
                Order.Status.DELIVERING,
                Order.Status.DELIVERED,
                Order.Status.CHANGED,
            ],
            product__seller=store.owner,
        ).exists()

        # Import here to avoid circular import
        from commerce.models import StoreReview

        StoreReview.objects.update_or_create(
            store=store,
            user=self.user,
            defaults={
                "rating": rating,
                "text": text.strip(),
                "is_verified_buyer": has_verified_purchase,
            },
        )

        return StoreReviewOperationResult(
            success=True,
            message="Отзыв о магазине сохранён",
        )

    def delete_store_review(self, store: SellerStore) -> StoreReviewOperationResult:
        """Delete store review created by current user."""
        from commerce.models import StoreReview

        deleted, _ = StoreReview.objects.filter(store=store, user=self.user).delete()

        return StoreReviewOperationResult(
            success=deleted > 0,
            message="Отзыв о магазине удалён" if deleted else "Отзыв не найден",
            deleted=deleted > 0,
        )
