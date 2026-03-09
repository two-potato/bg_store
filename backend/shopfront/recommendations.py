from __future__ import annotations

from collections import Counter

from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from catalog.models import Brand, Collection, Product
from orders.models import OrderItem
from shopfront.models import BrandSubscription, CategorySubscription, FavoriteProduct, RecentlyViewedProduct


User = get_user_model()


def record_recent_view(user, product: Product, limit: int = 24) -> None:
    if not getattr(user, "is_authenticated", False):
        return
    obj, created = RecentlyViewedProduct.objects.get_or_create(user=user, product=product)
    if not created:
        obj.save(update_fields=["updated_at"])
    stale_ids = list(
        RecentlyViewedProduct.objects.filter(user=user)
        .order_by("-updated_at")
        .values_list("id", flat=True)[limit:]
    )
    if stale_ids:
        RecentlyViewedProduct.objects.filter(id__in=stale_ids).delete()


def recently_viewed_ids_for_user(user, limit: int = 12) -> list[int]:
    if not getattr(user, "is_authenticated", False):
        return []
    return list(
        RecentlyViewedProduct.objects.filter(user=user)
        .order_by("-updated_at")
        .values_list("product_id", flat=True)[:limit]
    )


def frequently_bought_together_ids(product: Product, limit: int = 8) -> list[int]:
    order_ids = list(OrderItem.objects.filter(product=product).values_list("order_id", flat=True)[:150])
    if not order_ids:
        return []
    rows = (
        OrderItem.objects.filter(order_id__in=order_ids)
        .exclude(product_id=product.id)
        .values("product_id")
        .annotate(rank=Count("id"))
        .order_by("-rank", "product_id")[:limit]
    )
    return [row["product_id"] for row in rows]


def seller_cross_sell_ids(product: Product, limit: int = 8) -> list[int]:
    if not product.seller_id:
        return []
    qs = Product.objects.filter(seller_id=product.seller_id).exclude(id=product.id)
    if product.category_id:
        qs = qs.exclude(category_id=product.category_id)
    return list(qs.order_by("-is_promo", "-is_new", "name").values_list("id", flat=True)[:limit])


def personalized_home_sections(user, limit: int = 8) -> dict[str, list[int]]:
    if not getattr(user, "is_authenticated", False):
        return {"for_you": [], "based_on_lists": [], "brand_watch": []}

    favorites_ids = list(
        FavoriteProduct.objects.filter(user=user)
        .order_by("-created_at")
        .values_list("product_id", flat=True)[:24]
    )
    recent_ids = recently_viewed_ids_for_user(user, limit=24)
    seed_ids = favorites_ids + recent_ids

    for_you_counter = Counter()
    if seed_ids:
        product_map = {
            product.id: product
            for product in Product.objects.filter(id__in=seed_ids).select_related("brand", "category")
        }
        brand_ids = {product.brand_id for product in product_map.values() if product.brand_id}
        category_ids = {product.category_id for product in product_map.values() if product.category_id}
        if brand_ids or category_ids:
            for product_id in Product.objects.filter(
                Q(brand_id__in=brand_ids) | Q(category_id__in=category_ids)
            ).exclude(id__in=seed_ids).values_list("id", flat=True)[:100]:
                for_you_counter[product_id] += 1

    brand_watch_ids = list(
        Product.objects.filter(
            brand_id__in=BrandSubscription.objects.filter(user=user).values_list("brand_id", flat=True)
        )
        .order_by("-is_new", "-is_promo", "name")
        .values_list("id", flat=True)[:limit]
    )

    category_watch_ids = list(
        Product.objects.filter(
            category_id__in=CategorySubscription.objects.filter(user=user).values_list("category_id", flat=True)
        )
        .order_by("-is_new", "-is_promo", "name")
        .values_list("id", flat=True)[:limit]
    )

    ranked_for_you = [product_id for product_id, _score in for_you_counter.most_common(limit)]
    return {
        "for_you": ranked_for_you[:limit],
        "based_on_lists": recent_ids[:limit],
        "brand_watch": (brand_watch_ids + category_watch_ids)[:limit],
    }


def featured_collection_ids(limit: int = 3) -> list[int]:
    return list(
        Collection.objects.filter(is_active=True, is_featured=True)
        .order_by("-updated_at", "name")
        .values_list("id", flat=True)[:limit]
    )


def brand_highlight_ids(limit: int = 6) -> list[int]:
    return list(
        Brand.objects.annotate(products_count=Count("products"))
        .filter(products_count__gt=0)
        .order_by("-products_count", "name")
        .values_list("id", flat=True)[:limit]
    )
