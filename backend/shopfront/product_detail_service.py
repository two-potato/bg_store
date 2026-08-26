"""Service layer for product detail page context assembly."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.db.models import Prefetch

from catalog.models import Product, ProductImage
from catalog.offer_service import active_offer_queryset, apply_offer_snapshot
from commerce.models import SellerStore

from .catalog_selectors import (
    category_breadcrumbs as _category_breadcrumbs,
)
from .checkout_support import tracking_item_from_product as _tracking_item_from_product
from .models import BrandSubscription, CategorySubscription, FavoriteProduct
from .recommendation.service import (
    product_detail_recommendations,
    product_section_context,
)
from .review_service import build_reviews_context
from .views.utils_catalog import _product_url, _seller_store_for_user
from .views.utils_seo import (
    _absolute_url,
    _default_og_image,
    _product_json_ld,
    _product_primary_image,
    _seo_context,
    _truncate_text,
)
from .views.utils_state import (
    _compare_ids,
    _record_recently_viewed,
    _recently_viewed_products,
    _seller_rating_summary,
    _store_rating_summary,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser, User
    from django.http import HttpRequest


@dataclass(slots=True)
class ProductDetailContext:
    """Assembled context for product detail template."""

    product: Product
    reviews_context: dict[str, Any]
    seller_store: SellerStore | None
    active_offer: Any
    product_documents: list
    product_collections: list
    breadcrumbs: list
    compare_included: bool
    store_rating_avg: float
    store_rating_count: int
    seller_rating_avg: float
    seller_rating_count: int
    is_brand_subscribed: bool
    is_category_subscribed: bool
    recommendations: dict[str, Any]
    recently_viewed_products: list
    product_tracking_payload: str
    is_favorite: bool
    can_edit_product: bool
    offer_ladder: list[dict[str, Any]]
    trust_badges: list[dict[str, str]]
    product_quality: dict[str, Any]
    seo_context: dict[str, Any]


class ProductDetailPageService:
    """Assemble full product detail page context with reviews, recommendations, and SEO."""

    def __init__(self, request: HttpRequest) -> None:
        self.request = request
        self.user: User | AnonymousUser = request.user

    def _fetch_product_queryset(self, slug: str) -> Product | None:
        """Fetch product with all required relations optimized."""
        try:
            product = (
                Product.objects.select_related(
                    "brand",
                    "series",
                    "category",
                    "category__parent",
                    "seller",
                    "seller__seller_store",
                )
                .prefetch_related(
                    Prefetch(
                        "images",
                        queryset=ProductImage.objects.only(
                            "id", "product_id", "url", "alt", "ordering"
                        ).order_by("ordering", "id"),
                        to_attr="prefetched_images",
                    ),
                    "tags",
                    "documents",
                    "collections",
                    Prefetch("seller_offers", queryset=active_offer_queryset()),
                )
                .get(slug=slug)
            )
            return product
        except Product.DoesNotExist:
            return None

    def _prepare_subscriptions(self, product: Product) -> tuple[bool, bool]:
        """Check brand and category subscriptions for current user."""
        brand_subscribed = False
        category_subscribed = False

        if self.user.is_authenticated:
            if product.brand_id:
                brand_subscribed = BrandSubscription.objects.filter(
                    user=self.user, brand_id=product.brand_id
                ).exists()
            if product.category_id:
                category_subscribed = CategorySubscription.objects.filter(
                    user=self.user, category_id=product.category_id
                ).exists()

        return brand_subscribed, category_subscribed

    def _prepare_seller_context(self, product: Product) -> tuple[Any, dict, dict]:
        """Get seller store, seller rating, and store rating."""
        seller_store = getattr(
            getattr(product, "active_offer", None), "seller_store", None
        ) or _seller_store_for_user(product.seller if product.seller_id else None)
        seller_summary = _seller_rating_summary(getattr(product, "seller_id", None))
        store_summary = _store_rating_summary(seller_store)
        return seller_store, seller_summary, store_summary

    def _prepare_favorite(self, product: Product) -> bool:
        """Check if product is in user's favorites."""
        if not self.user.is_authenticated:
            return False
        return FavoriteProduct.objects.filter(user=self.user, product=product).exists()

    def _prepare_tracking_payload(self, product: Product) -> str:
        """Build analytics tracking payload."""
        return json.dumps(
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

    def _prepare_offer_ladder(self, product: Product) -> list[dict[str, Any]]:
        """Build a compact multi-offer ladder for decision support on PDP."""
        offers = list(getattr(product, "_prefetched_objects_cache", {}).get("seller_offers", []) or [])
        ladder: list[dict[str, Any]] = []
        if not offers:
            return ladder

        lowest_price = min(offer.price for offer in offers)
        fastest_eta = min(max(0, int(offer.lead_time_days or 0)) for offer in offers)
        lowest_moq = min(max(1, int(offer.min_order_qty or 1)) for offer in offers)
        featured_offer_id = next((offer.id for offer in offers if getattr(offer, "is_featured", False)), None)

        for offer in offers[:4]:
            store = getattr(offer, "seller_store", None)
            seller_summary = _seller_rating_summary(getattr(offer, "seller_id", None))
            store_summary = _store_rating_summary(store)
            stock_qty = max(0, int(getattr(offer, "available_stock_qty", 0) or 0))
            eta_days = max(0, int(offer.lead_time_days or 0))
            moq = max(1, int(offer.min_order_qty or 1))

            highlights: list[str] = []
            if offer.price == lowest_price:
                highlights.append("Лучшая цена")
            if eta_days == fastest_eta:
                highlights.append("Самая быстрая поставка")
            if moq == lowest_moq:
                highlights.append("Минимальный MOQ")
            if featured_offer_id and offer.id == featured_offer_id:
                highlights.append("Рекомендованный оффер")
            if store and store.moderation_status == store.ModerationStatus.APPROVED:
                highlights.append("Проверенный магазин")

            ladder.append(
                {
                    "id": offer.id,
                    "seller_name": getattr(store, "name", "") or getattr(offer.seller, "username", "Поставщик"),
                    "seller_slug": getattr(store, "slug", ""),
                    "price": offer.price,
                    "stock_qty": stock_qty,
                    "lead_time_days": eta_days,
                    "min_order_qty": moq,
                    "sla_target_hours": getattr(store, "sla_target_hours", 0) or 0,
                    "seller_rating_avg": seller_summary["rating_avg"],
                    "seller_rating_count": seller_summary["rating_count"],
                    "store_rating_avg": store_summary["rating_avg"],
                    "store_rating_count": store_summary["rating_count"],
                    "highlights": highlights[:3],
                    "is_best_price": offer.price == lowest_price,
                    "is_fastest": eta_days == fastest_eta,
                    "is_lowest_moq": moq == lowest_moq,
                    "is_verified_store": bool(
                        store and store.moderation_status == store.ModerationStatus.APPROVED
                    ),
                }
            )
        return ladder

    def _prepare_quality(self, product: Product, seller_store: SellerStore | None) -> dict[str, Any]:
        """Build product content-quality score used for trust-critical surfaces."""
        images = list(getattr(product, "prefetched_images", []) or [])
        documents = list(product.documents.all())
        attributes_count = len([value for value in (product.attributes or {}).values() if value not in (None, "", [], {})])
        checks = [
            {
                "key": "images",
                "label": "Фото",
                "detail": f"{len(images)} фото",
                "ok": len(images) > 0,
            },
            {
                "key": "documents",
                "label": "Документы",
                "detail": f"{len(documents)} файла",
                "ok": len(documents) > 0,
            },
            {
                "key": "attributes",
                "label": "Атрибуты",
                "detail": f"{attributes_count} заполнено",
                "ok": attributes_count >= 3,
            },
            {
                "key": "commercial",
                "label": "ETA / MOQ",
                "detail": f"{product.display_lead_time_days or 1}-{product.display_lead_time_days or 2} дн. · MOQ {product.display_min_order_qty or 1}",
                "ok": bool(product.display_min_order_qty) and product.display_stock_qty >= 0,
            },
            {
                "key": "seller",
                "label": "Поставщик",
                "detail": getattr(seller_store, "name", "") or "Указан продавец",
                "ok": bool(getattr(product, "seller_id", None)),
            },
        ]
        completed = sum(1 for check in checks if check["ok"])
        return {
            "score": int(round((completed / len(checks)) * 100)),
            "checks": checks,
            "missing_count": len(checks) - completed,
        }

    def _prepare_trust_badges(
        self,
        product: Product,
        seller_store: SellerStore | None,
        offer_ladder: list[dict[str, Any]],
        quality: dict[str, Any],
        seller_summary: dict[str, Any],
        store_summary: dict[str, Any],
    ) -> list[dict[str, str]]:
        """Build explainable trust badges with data-backed explanations."""
        badges: list[dict[str, str]] = []
        if offer_ladder and offer_ladder[0]["is_best_price"]:
            badges.append(
                {
                    "label": "Servio Pick",
                    "detail": "Оффер сейчас лидирует по цене среди доступных предложений в карточке.",
                }
            )
        if product.display_lead_time_days and int(product.display_lead_time_days) <= 2:
            badges.append(
                {
                    "label": "Fast ship",
                    "detail": f"Ожидаемая поставка {product.display_lead_time_days} дн. по активному офферу.",
                }
            )
        if quality["score"] >= 80 and any(check["key"] == "documents" and check["ok"] for check in quality["checks"]):
            badges.append(
                {
                    "label": "Verified docs",
                    "detail": "У карточки есть документы и заполненный коммерческий контур.",
                }
            )
        if seller_store and seller_store.moderation_status == seller_store.ModerationStatus.APPROVED:
            badges.append(
                {
                    "label": "Stable ETA",
                    "detail": f"Магазин прошёл модерацию, целевой SLA {seller_store.sla_target_hours} ч.",
                }
            )
        if (
            seller_summary["rating_count"] >= 3
            and float(seller_summary["rating_avg"] or 0) >= 4.5
        ) or (
            store_summary["rating_count"] >= 3
            and float(store_summary["rating_avg"] or 0) >= 4.5
        ):
            badges.append(
                {
                    "label": "Top seller",
                    "detail": "Высокий рейтинг продавца или магазина по отзывам покупателей.",
                }
            )
        if getattr(product, "rating_count", 0) >= 5 and float(getattr(product, "rating_avg", 0) or 0) >= 4.5:
            badges.append(
                {
                    "label": "Best repeat purchase",
                    "detail": "Карточка уже набрала устойчивые положительные оценки покупателей.",
                }
            )
        return badges[:5]

    def _prepare_seo_context(
        self, product: Product, seller_store: SellerStore | None
    ) -> dict[str, Any]:
        """Build SEO context for product detail page."""
        primary_image = _product_primary_image(product)
        return _seo_context(
            self.request,
            title=f"{product.name} — {getattr(product.brand, 'name', 'Servio')} | Servio",
            description=_truncate_text(
                product.description
                or f"{product.name} в каталоге Servio: поставки для ресторанов, кафе, баров и гостиничных проектов.",
                170,
            ),
            canonical=_absolute_url(self.request, _product_url(product)),
            og_type="product",
            og_image=(
                _absolute_url(self.request, primary_image.url)
                if primary_image
                else _default_og_image(self.request)
            ),
            json_ld=_product_json_ld(self.request, product, seller_store=seller_store),
        )

    def build_context(self, slug: str) -> ProductDetailContext | None:
        """Build complete product detail context."""
        product = self._fetch_product_queryset(slug)
        if product is None:
            return None

        # Record view for analytics
        _record_recently_viewed(self.request, product)

        # Apply offer snapshots
        apply_offer_snapshot([product])

        # Build modular context parts
        reviews_context = build_reviews_context(
            product, self.user, seller_rating_summary=_seller_rating_summary
        )
        seller_store, seller_summary, store_summary = self._prepare_seller_context(
            product
        )
        brand_subscribed, category_subscribed = self._prepare_subscriptions(product)
        compare_included = product.id in _compare_ids(self.request)
        is_favorite = self._prepare_favorite(product)
        can_edit = bool(
            self.user.is_authenticated
            and (
                self.user.is_staff
                or self.user.is_superuser
                or product.seller_id == self.user.id
            )
        )
        tracking_payload = self._prepare_tracking_payload(product)
        recommendations = product_detail_recommendations(
            product, user=self.user, request=self.request, limit=12
        )
        recently_viewed = _recently_viewed_products(
            self.request, exclude_product_id=product.id, limit=8
        )
        offer_ladder = self._prepare_offer_ladder(product)
        quality = self._prepare_quality(product, seller_store)
        trust_badges = self._prepare_trust_badges(
            product,
            seller_store,
            offer_ladder,
            quality,
            seller_summary,
            store_summary,
        )
        seo_context = self._prepare_seo_context(product, seller_store)

        return ProductDetailContext(
            product=product,
            reviews_context=reviews_context,
            seller_store=seller_store,
            active_offer=getattr(product, "active_offer", None),
            product_documents=list(product.documents.all()),
            product_collections=list(product.collections.all()[:6]),
            breadcrumbs=_category_breadcrumbs(getattr(product, "category", None)),
            compare_included=compare_included,
            store_rating_avg=store_summary["rating_avg"],
            store_rating_count=store_summary["rating_count"],
            seller_rating_avg=seller_summary["rating_avg"],
            seller_rating_count=seller_summary["rating_count"],
            is_brand_subscribed=brand_subscribed,
            is_category_subscribed=category_subscribed,
            recommendations=recommendations,
            recently_viewed_products=recently_viewed,
            product_tracking_payload=tracking_payload,
            is_favorite=is_favorite,
            can_edit_product=can_edit,
            offer_ladder=offer_ladder,
            trust_badges=trust_badges,
            product_quality=quality,
            seo_context=seo_context,
        )


class ProductRecommendationSectionService:
    """Build recommendation section context for AJAX endpoints."""

    def __init__(self, request: HttpRequest) -> None:
        self.request = request
        self.user: User | AnonymousUser = request.user

    def build_section_context(self, slug: str, section: str) -> dict[str, Any] | None:
        """Build context for a specific recommendation section."""
        try:
            product = Product.objects.only(
                "id", "seller_id", "category_id", "brand_id", "name", "slug"
            ).get(slug=slug)
        except Product.DoesNotExist:
            return None

        return product_section_context(
            product, section, user=self.user, request=self.request
        )
