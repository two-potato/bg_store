"""Catalog and shared cache helpers for shopfront views."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.urls import reverse

from catalog.models import Brand, Category, Product, Tag
from commerce.models import SellerStore

from ..catalog_selectors import category_slug_path as _category_slug_path
from .constants import log


@dataclass(slots=True)
class CatalogRequestParams:
    """Normalized catalog query parameters reused across storefront views."""

    brand: str
    category: str
    seller: str
    series: str
    q: str
    tag: str
    availability: str
    delivery_eta: str
    min_price: Decimal | None
    max_price: Decimal | None
    sort: str
    page: int

    @classmethod
    def from_request(cls, request) -> "CatalogRequestParams":
        """Parse and normalize catalog GET params from request."""
        try:
            page = int(request.GET.get("page") or 1)
        except (TypeError, ValueError):
            page = 1
        return cls(
            brand=str(request.GET.get("brand") or "").strip(),
            category=str(request.GET.get("category") or "").strip(),
            seller=str(request.GET.get("seller") or "").strip(),
            series=str(request.GET.get("series") or "").strip(),
            q=str(request.GET.get("q") or "").strip(),
            tag=str(request.GET.get("tag") or request.GET.get("tag_slug") or "").strip(),
            availability=str(request.GET.get("availability") or "").strip(),
            delivery_eta=str(request.GET.get("delivery_eta") or "").strip(),
            min_price=_parse_decimal_filter(request.GET.get("min_price")),
            max_price=_parse_decimal_filter(request.GET.get("max_price")),
            sort=str(request.GET.get("sort") or "").strip(),
            page=max(1, page),
        )

    def base_query_params(self) -> dict[str, str]:
        """Return current filters without page for pagination links."""
        params = {}
        for key in (
            "q",
            "brand",
            "category",
            "seller",
            "series",
            "tag",
            "availability",
            "delivery_eta",
            "sort",
        ):
            value = getattr(self, key)
            if value:
                params[key] = value
        if self.min_price is not None:
            params["min_price"] = str(self.min_price)
        if self.max_price is not None:
            params["max_price"] = str(self.max_price)
        return params


def _cache_get(key, default=None):
    """Read from cache with defensive logging."""
    try:
        return cache.get(key, default)
    except Exception:
        log.warning("cache_get_failed", extra={"cache_key": key}, exc_info=True)
        return default


def _cache_set(key, value, timeout):
    """Write to cache with defensive logging."""
    try:
        cache.set(key, value, timeout=timeout)
    except Exception:
        log.warning("cache_set_failed", extra={"cache_key": key}, exc_info=True)


def _parse_decimal_filter(raw_value: str | None) -> Decimal | None:
    """Parse decimal filter input used in catalog query params."""
    value = (raw_value or "").strip().replace(",", ".")
    if not value:
        return None
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed.quantize(Decimal("0.01"))


def _new_idempotency_key() -> str:
    """Generate a new checkout idempotency key."""
    return uuid4().hex


def _visible_brand_filter_options(brands, facet_brand_options, selected_brand):
    """Return a bounded list of visible brand filter options."""
    limit = max(8, int(getattr(settings, "CATALOG_FILTER_BRAND_LIMIT", 24)))
    selected_ids = {option["id"] for option in facet_brand_options}
    if selected_brand is not None:
        selected_ids.add(selected_brand.id)
    selected = [brand for brand in brands if brand.id in selected_ids]
    if len(selected) >= limit:
        return selected[:limit]
    selected_set = {brand.id for brand in selected}
    for brand in brands:
        if brand.id in selected_set:
            continue
        selected.append(brand)
        if len(selected) >= limit:
            break
    return selected


def _visible_tag_filter_options(tags, selected_tag):
    """Return a bounded list of visible tag filter options."""
    limit = max(8, int(getattr(settings, "CATALOG_FILTER_TAG_LIMIT", 24)))
    if not selected_tag:
        return tags[:limit]
    selected = [tag for tag in tags if str(tag.id) == str(selected_tag) or tag.slug == str(selected_tag)]
    selected_ids = {tag.id for tag in selected}
    for tag in tags:
        if tag.id in selected_ids:
            continue
        selected.append(tag)
        if len(selected) >= limit:
            break
    return selected[:limit]


def _catalog_filter_suggestion_limit() -> int:
    """Return configured upper bound for filter suggestion endpoint."""
    return max(5, min(20, int(getattr(settings, "CATALOG_FILTER_SUGGESTION_LIMIT", 8))))


def _catalog_filter_cache_timeout() -> int:
    """Return catalog filter cache TTL."""
    return int(getattr(settings, "CACHE_TTL_CATALOG_FILTERS", 900))


def _cached_catalog_brands():
    """Return cached brand list for catalog filters."""
    latest_id = Brand.objects.order_by("-id").values_list("id", flat=True).first() or 0
    brands = _cache_get(f"shopfront:catalog:brands:v2:{latest_id}")
    if brands is None:
        brands = list(Brand.objects.only("id", "name").order_by("name"))
        _cache_set(f"shopfront:catalog:brands:v2:{latest_id}", brands, timeout=_catalog_filter_cache_timeout())
    return brands


def _cached_catalog_categories():
    """Return cached category list for catalog filters."""
    latest_id = Category.objects.order_by("-id").values_list("id", flat=True).first() or 0
    categories = _cache_get(f"shopfront:catalog:categories:v2:{latest_id}")
    if categories is None:
        categories = list(
            Category.objects.select_related("parent")
            .exclude(name__startswith="HoReCa направление")
            .only("id", "name", "slug", "parent_id")
            .order_by("parent_id", "name", "id")
        )
        _cache_set(
            f"shopfront:catalog:categories:v2:{latest_id}",
            categories,
            timeout=_catalog_filter_cache_timeout(),
        )
    return categories


def _cached_catalog_tags():
    """Return cached tag list for catalog filters."""
    latest_id = Tag.objects.order_by("-id").values_list("id", flat=True).first() or 0
    tags = _cache_get(f"shopfront:catalog:tags:v3:{latest_id}")
    if tags is None:
        tags = list(Tag.objects.only("id", "name", "slug").order_by("name"))
        _cache_set(f"shopfront:catalog:tags:v3:{latest_id}", tags, timeout=_catalog_filter_cache_timeout())
    return tags


def _category_breadcrumb_label_map(categories) -> dict[int, str]:
    """Build breadcrumb labels for category filter autosuggest."""
    by_id = {category.id: category for category in categories}
    labels: dict[int, str] = {}
    for category in categories:
        parts = []
        cursor = category
        safety = 0
        while cursor is not None and safety < 12:
            parts.append(cursor.name)
            cursor = by_id.get(cursor.parent_id)
            safety += 1
        labels[category.id] = " / ".join(reversed(parts))
    return labels


def _category_path(category: Category | None) -> str:
    """Return slash-based category path for URLs."""
    return _category_slug_path(category)


def _category_url(category: Category | None) -> str:
    """Return category URL for canonical links and navigation."""
    if category is None:
        return reverse("categories")
    return reverse("category_detail", kwargs={"category_slug": _category_path(category)})


def _product_url(product: Product) -> str:
    """Return canonical product URL."""
    return reverse("product", kwargs={"slug": product.slug})


def _seller_store_for_user(user):
    """Return seller store for user, preferring loaded relations to avoid N+1."""
    if user is None:
        return None
    try:
        store = user.seller_store
        if store is not None:
            return store
    except Exception:
        pass
    return (
        SellerStore.objects.select_related("owner", "owner__profile", "legal_entity")
        .filter(owner=user)
        .first()
    )


def _vendor_slug_for_user(user) -> str:
    """Resolve vendor slug using seller store first, then user profile."""
    store = _seller_store_for_user(user)
    if store is not None and getattr(store, "slug", ""):
        return store.slug
    profile = getattr(user, "profile", None)
    if profile is not None and getattr(profile, "slug", ""):
        return profile.slug
    return ""


def _vendor_url(store: SellerStore | None = None, user=None) -> str:
    """Build vendor detail URL from store or user context."""
    if store is not None and getattr(store, "slug", ""):
        return reverse("vendor_detail", kwargs={"vendor_slug": store.slug})
    if user is not None:
        slug = _vendor_slug_for_user(user)
        if slug:
            return reverse("vendor_detail", kwargs={"vendor_slug": slug})
    return reverse("vendors")


def _selected_tag_object(selected_tag, tags):
    """Resolve selected tag object by id or slug."""
    if not selected_tag:
        return None
    selected_raw = str(selected_tag)
    for tag in tags:
        if str(tag.id) == selected_raw or tag.slug == selected_raw:
            return tag
    if selected_raw.isdigit():
        return Tag.objects.only("id", "name", "slug").filter(id=int(selected_raw)).first()
    return Tag.objects.only("id", "name", "slug").filter(slug=selected_raw).first()
