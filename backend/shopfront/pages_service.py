"""Service layer for merchandising pages (brands, categories, collections)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.db.models import Count
from django.http import Http404

from catalog.models import Brand, Category, Collection, Product

from .catalog_selectors import (
    category_breadcrumbs as _category_breadcrumbs,
    category_descendant_ids as _category_descendant_ids,
    category_slug_path as _category_slug_path,
    ordered_products_with_related as _ordered_products_with_related,
)
from .models import BrandSubscription
from .views.utils_seo import (
    _absolute_url,
    _seo_context,
    _truncate_text,
)
from django.urls import reverse

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser, User
    from django.http import HttpRequest


@dataclass(slots=True)
class BrandDetailContext:
    """Context for brand detail page."""

    brand: Brand
    products: list[Product]
    child_categories: list[Category]
    featured_collections: list[Collection]
    is_brand_subscribed: bool
    seo_context: dict[str, Any]


@dataclass(slots=True)
class CategoryDetailContext:
    """Context for category detail page."""

    category: Category
    products: list[Product]
    breadcrumbs: list
    child_categories: list[Category]
    featured_brands: list[Brand]
    seo_context: dict[str, Any]


@dataclass(slots=True)
class CollectionDetailContext:
    """Context for collection detail page."""

    collection: Collection
    products: list[Product]
    related_collections: list[Collection]
    seo_context: dict[str, Any]


class BrandDetailService:
    """Assemble brand detail page context."""

    def __init__(self, request: HttpRequest) -> None:
        self.request = request
        self.user: User | AnonymousUser = request.user

    def build_context(self, brand_slug: str) -> BrandDetailContext | None:
        """Build complete brand detail context."""
        try:
            brand = Brand.objects.annotate(
                products_count=Count("products", distinct=True),
                categories_count=Count("products__category", distinct=True),
                collections_count=Count("products__collections", distinct=True),
            ).get(slug=brand_slug)
        except Brand.DoesNotExist:
            return None

        # Fetch related products
        product_ids = list(
            Product.objects.filter(brand=brand)
            .order_by("-is_new", "name")
            .values_list("id", flat=True)[:60]
        )
        products = _ordered_products_with_related(product_ids, include_rating=True)

        # Fetch related categories and collections
        child_categories = list(
            Category.objects.filter(products__brand=brand)
            .distinct()
            .order_by("name")[:8]
        )
        featured_collections = list(
            Collection.objects.filter(is_active=True, items__product__brand=brand)
            .distinct()
            .order_by("-is_featured", "name")[:4]
        )

        # Check subscription
        is_brand_subscribed = bool(
            self.user.is_authenticated
            and BrandSubscription.objects.filter(user=self.user, brand=brand).exists()
        )

        # Build SEO context
        seo_context = _seo_context(
            self.request,
            title=f"{brand.name} — каталог бренда | Servio",
            description=_truncate_text(
                brand.description
                or f"Ассортимент бренда {brand.name} в каталоге Servio для профессиональных закупок HoReCa.",
                160,
            ),
            canonical=_absolute_url(
                self.request,
                reverse("brand_detail", kwargs={"brand_slug": brand.slug}),
            ),
        )

        return BrandDetailContext(
            brand=brand,
            products=products,
            child_categories=child_categories,
            featured_collections=featured_collections,
            is_brand_subscribed=is_brand_subscribed,
            seo_context=seo_context,
        )


class CategoryDetailService:
    """Assemble category detail page context."""

    def __init__(self, request: HttpRequest) -> None:
        self.request = request
        self.user: User | AnonymousUser = request.user

    def resolve_category_by_path(self, raw_path: str) -> Category:
        """Resolve category from slash-separated path."""
        parts = [
            part.strip() for part in str(raw_path or "").split("/") if part.strip()
        ]
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

    def build_context(self, category_slug: str) -> CategoryDetailContext | None:
        """Build complete category detail context."""
        try:
            category = self.resolve_category_by_path(category_slug)
        except Http404:
            return None

        # Fetch related products
        category_ids = _category_descendant_ids(category)
        product_ids = list(
            Product.objects.filter(category_id__in=category_ids)
            .order_by("-is_new", "name")
            .values_list("id", flat=True)[:80]
        )
        products = _ordered_products_with_related(product_ids, include_rating=True)

        # Fetch related entities
        breadcrumbs = _category_breadcrumbs(category)
        child_categories = list(category.children.order_by("name")[:12])
        featured_brands = list(
            Brand.objects.filter(products__category_id__in=category_ids)
            .distinct()
            .order_by("name")[:8]
        )

        # Build SEO context
        seo_context = _seo_context(
            self.request,
            title=f"{category.meta_title or category.name} — категория Servio",
            description=_truncate_text(
                category.meta_description
                or category.description
                or category.hero_text
                or f"Категория {category.name} в каталоге Servio.",
                160,
            ),
            canonical=_absolute_url(
                self.request,
                reverse(
                    "category_detail",
                    kwargs={"category_slug": _category_slug_path(category)},
                ),
            ),
        )

        return CategoryDetailContext(
            category=category,
            products=products,
            breadcrumbs=breadcrumbs,
            child_categories=child_categories,
            featured_brands=featured_brands,
            seo_context=seo_context,
        )


class CollectionDetailService:
    """Assemble collection detail page context."""

    def __init__(self, request: HttpRequest) -> None:
        self.request = request
        self.user: User | AnonymousUser = request.user

    def build_context(self, collection_slug: str) -> CollectionDetailContext | None:
        """Build complete collection detail context."""
        try:
            collection = Collection.objects.get(is_active=True, slug=collection_slug)
        except Collection.DoesNotExist:
            return None

        # Fetch products in collection
        product_ids = list(
            collection.items.order_by("ordering", "id").values_list(
                "product_id", flat=True
            )[:80]
        )
        products = _ordered_products_with_related(product_ids, include_rating=True)

        # Fetch related collections
        related_collections = list(
            Collection.objects.filter(is_active=True, is_featured=True)
            .exclude(id=collection.id)
            .order_by("-updated_at", "name")[:3]
        )

        # Build SEO context
        seo_context = _seo_context(
            self.request,
            title=f"{collection.name} — коллекция Servio",
            description=_truncate_text(
                collection.description
                or collection.hero_text
                or f"Коллекция {collection.name} в Servio.",
                160,
            ),
            canonical=_absolute_url(
                self.request,
                reverse(
                    "collection_detail", kwargs={"collection_slug": collection.slug}
                ),
            ),
        )

        return CollectionDetailContext(
            collection=collection,
            products=products,
            related_collections=related_collections,
            seo_context=seo_context,
        )
