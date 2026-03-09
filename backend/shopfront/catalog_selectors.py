import logging

from django.conf import settings
from django.core.cache import cache
from django.db.models import Avg, Case, Count, FloatField, IntegerField, Min, Max, Prefetch, Value, When
from django.db.models.functions import Coalesce

from catalog.models import Brand, Category, Collection, Product, ProductImage
from catalog.offer_service import active_offer_queryset, apply_offer_snapshot

log = logging.getLogger("shopfront")


def _cache_get(key, default=None):
    try:
        return cache.get(key, default)
    except Exception:
        log.warning("cache_get_failed", extra={"cache_key": key}, exc_info=True)
        return default


def _cache_set(key, value, timeout):
    try:
        cache.set(key, value, timeout=timeout)
    except Exception:
        log.warning("cache_set_failed", extra={"cache_key": key}, exc_info=True)


def category_breadcrumbs(category: Category | None) -> list[Category]:
    trail: list[Category] = []
    current = category
    safety = 0
    while current is not None and safety < 12:
        trail.append(current)
        current = getattr(current, "parent", None)
        safety += 1
    return list(reversed(trail))


def category_descendant_ids(category: Category | None) -> list[int]:
    if category is None:
        return []
    ids: list[int] = [category.id]
    frontier = [category.id]
    safety = 0
    while frontier and safety < 20:
        children = list(Category.objects.filter(parent_id__in=frontier).values_list("id", flat=True))
        if not children:
            break
        ids.extend(children)
        frontier = children
        safety += 1
    return ids


def category_option_rows(categories: list[Category]) -> list[dict]:
    by_parent: dict[int | None, list[Category]] = {}
    for category in categories:
        by_parent.setdefault(category.parent_id, []).append(category)
    for children in by_parent.values():
        children.sort(key=lambda item: (item.name or "").lower())

    rows: list[dict] = []

    def walk(parent_id: int | None, depth: int) -> None:
        for node in by_parent.get(parent_id, []):
            rows.append(
                {
                    "id": node.id,
                    "slug": node.slug,
                    "name": node.name,
                    "depth": depth,
                    "label": f'{"\u00A0\u00A0" * depth}{node.name}',
                }
            )
            walk(node.id, depth + 1)

    walk(None, 0)
    return rows


def facet_option_counts(qs, field_name: str, *, label_field: str = "name", limit: int = 12) -> list[dict]:
    values = (
        qs.exclude(**{f"{field_name}__isnull": True})
        .values(f"{field_name}_id", f"{field_name}__{label_field}")
        .annotate(count=Count("id"))
        .order_by("-count", f"{field_name}__{label_field}")[:limit]
    )
    options = []
    for row in values:
        entity_id = row.get(f"{field_name}_id")
        label = row.get(f"{field_name}__{label_field}") or ""
        if not entity_id or not label:
            continue
        options.append({"id": entity_id, "label": label, "count": row.get("count", 0)})
    return options


def seller_facet_counts(qs, limit: int = 10) -> list[dict]:
    values = (
        qs.exclude(seller__seller_store__isnull=True)
        .values("seller_id", "seller__seller_store__name", "seller__seller_store__slug")
        .annotate(count=Count("id"))
        .order_by("-count", "seller__seller_store__name")[:limit]
    )
    options = []
    for row in values:
        if not row.get("seller_id"):
            continue
        options.append(
            {
                "id": row["seller_id"],
                "slug": row.get("seller__seller_store__slug", "") or "",
                "label": row.get("seller__seller_store__name", "") or "",
                "count": row.get("count", 0),
            }
        )
    return options


def with_rating(qs):
    return qs.annotate(
        rating_avg=Coalesce(Avg("reviews__rating"), Value(0.0), output_field=FloatField()),
        rating_count=Count("reviews", distinct=True),
    )


def ordered_products_with_related(product_ids, include_rating: bool = True):
    if not product_ids:
        return []
    order_case = Case(
        *[When(id=pid, then=pos) for pos, pid in enumerate(product_ids)],
        default=len(product_ids),
        output_field=IntegerField(),
    )
    base_qs = (
        Product.objects.filter(id__in=product_ids)
        .only(
            "id",
            "slug",
            "name",
            "price",
            "stock_qty",
            "min_order_qty",
            "lead_time_days",
            "pack_qty",
            "unit",
            "material",
            "volume_ml",
            "is_new",
            "is_promo",
            "brand__name",
            "brand__slug",
            "series__name",
            "category__name",
            "category__slug",
            "seller__seller_store__slug",
            "seller__seller_store__name",
        )
        .select_related("brand", "series", "category", "seller", "seller__seller_store")
        .prefetch_related(
            Prefetch(
                "images",
                queryset=ProductImage.objects.only("id", "product_id", "url", "alt", "ordering").order_by("ordering", "id"),
                to_attr="prefetched_images",
            ),
            Prefetch(
                "collections",
                queryset=Collection.objects.only("id", "name", "slug").order_by("-is_featured", "name"),
            ),
            Prefetch("seller_offers", queryset=active_offer_queryset()),
        )
    )
    if include_rating:
        base_qs = with_rating(base_qs)
    return apply_offer_snapshot(list(base_qs.order_by(order_case)))


def cached_home_product_ids(limit: int = 12):
    key = f"shopfront:home:product_ids:v2:{limit}"
    ids = _cache_get(key)
    if ids is None:
        ids = list(Product.objects.order_by("-is_new", "name", "id").values_list("id", flat=True)[:limit])
        _cache_set(key, ids, timeout=getattr(settings, "CACHE_TTL_HOME", 180))
    return ids


def cached_home_category_ids(limit: int = 8):
    key = f"shopfront:home:category_ids:v1:{limit}"
    ids = _cache_get(key)
    if ids is None:
        ids = list(
            Category.objects.filter(parent__isnull=True)
            .exclude(name__startswith="HoReCa направление")
            .order_by("id")
            .values_list("id", flat=True)[:limit]
        )
        _cache_set(key, ids, timeout=getattr(settings, "CACHE_TTL_HOME", 180))
    return ids


def cached_catalog_default_page_ids(page: int, page_size: int):
    key = f"shopfront:catalog:default_page_ids:v3:{page}:{page_size}"
    ids = _cache_get(key)
    if ids is None:
        offset = max(0, page - 1) * page_size
        ids = list(
            Product.objects.order_by("-is_new", "name", "id").values_list("id", flat=True)[offset : offset + page_size]
        )
        _cache_set(key, ids, timeout=getattr(settings, "CACHE_TTL_CATALOG_API", 120))
    return ids


def cached_catalog_default_total_count():
    key = "shopfront:catalog:default_total_count:v3"
    count = _cache_get(key)
    if count is None:
        count = Product.objects.count()
        _cache_set(key, count, timeout=getattr(settings, "CACHE_TTL_CATALOG_API", 120))
    return count


def catalog_price_stats(qs):
    return qs.aggregate(min_price=Min("price"), max_price=Max("price"))
