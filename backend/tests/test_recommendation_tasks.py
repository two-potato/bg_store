import pytest
from django.core.management import call_command
from django.contrib.auth import get_user_model

from catalog.models import Brand, Category, Product
from orders.models import Order, OrderItem
from shopfront.models import (
    FavoriteProduct,
    RecommendationPopularitySnapshot,
    RecommendationProductAffinity,
    RecommendationReplenishmentProfile,
    RecommendationSet,
    RecommendationUserAffinity,
    RecentlyViewedProduct,
)
from shopfront.tasks import (
    refresh_recommendation_affinities,
    refresh_recommendation_popularity,
    refresh_recommendation_replenishment,
    refresh_recommendation_sets,
    refresh_recommendation_user_affinity,
)


pytestmark = pytest.mark.django_db


def _make_product(*, seller, brand, category, sku: str, name: str, stock_qty: int = 10):
    return Product.objects.create(
        seller=seller,
        brand=brand,
        category=category,
        sku=sku,
        name=name,
        price="120.00",
        stock_qty=stock_qty,
    )


def test_refresh_recommendation_popularity_and_sets(user):
    seller = get_user_model().objects.create_user(username="seller_task_1", password="pass")
    brand = Brand.objects.create(name="Brand Task A")
    category = Category.objects.create(name="Category Task A")
    p1 = _make_product(seller=seller, brand=brand, category=category, sku="22220001", name="Popular A")
    p2 = _make_product(seller=seller, brand=brand, category=category, sku="22220002", name="Popular B")
    FavoriteProduct.objects.create(user=user, product=p1)
    RecentlyViewedProduct.objects.create(user=user, product=p1)
    RecentlyViewedProduct.objects.create(user=user, product=p2)

    refresh_recommendation_popularity()
    refresh_recommendation_sets()

    assert RecommendationPopularitySnapshot.objects.filter(
        scope_type=RecommendationPopularitySnapshot.ScopeType.GLOBAL,
        product=p1,
    ).exists()
    assert RecommendationSet.objects.filter(kind="home_popular").exists()


def test_refresh_recommendation_affinities_builds_copurchase_edges(user):
    seller = get_user_model().objects.create_user(username="seller_task_2", password="pass")
    brand = Brand.objects.create(name="Brand Task B")
    category = Category.objects.create(name="Category Task B")
    p1 = _make_product(seller=seller, brand=brand, category=category, sku="22220011", name="Edge A")
    p2 = _make_product(seller=seller, brand=brand, category=category, sku="22220012", name="Edge B")
    order = Order.objects.create(placed_by=user, customer_type=Order.CustomerType.COMPANY)
    OrderItem.objects.create(order=order, product=p1, name=p1.name, price=p1.price, qty=1)
    OrderItem.objects.create(order=order, product=p2, name=p2.name, price=p2.price, qty=1)

    refresh_recommendation_affinities()

    edge = RecommendationProductAffinity.objects.get(
        source_product=p1,
        target_product=p2,
        affinity_type=RecommendationProductAffinity.AffinityType.CO_PURCHASE,
    )
    assert edge.orders_count == 1


def test_refresh_recommendations_management_command(user):
    seller = get_user_model().objects.create_user(username="seller_task_3", password="pass")
    brand = Brand.objects.create(name="Brand Task C")
    category = Category.objects.create(name="Category Task C")
    p1 = _make_product(seller=seller, brand=brand, category=category, sku="22220021", name="Cmd A")
    FavoriteProduct.objects.create(user=user, product=p1)
    RecentlyViewedProduct.objects.create(user=user, product=p1)

    call_command("refresh_recommendations", window="7d", limit=20, set_limit=6)

    assert RecommendationPopularitySnapshot.objects.exists()
    assert RecommendationSet.objects.exists()


def test_refresh_recommendation_user_affinity_and_replenishment(user):
    seller = get_user_model().objects.create_user(username="seller_task_4", password="pass")
    brand = Brand.objects.create(name="Brand Task D")
    category = Category.objects.create(name="Category Task D")
    p1 = _make_product(seller=seller, brand=brand, category=category, sku="22220031", name="Affinity A")
    FavoriteProduct.objects.create(user=user, product=p1)
    RecentlyViewedProduct.objects.create(user=user, product=p1)
    order = Order.objects.create(placed_by=user, customer_type=Order.CustomerType.COMPANY)
    OrderItem.objects.create(order=order, product=p1, name=p1.name, price=p1.price, qty=3)

    refresh_recommendation_user_affinity()
    refresh_recommendation_replenishment()

    assert RecommendationUserAffinity.objects.filter(user=user, dimension=RecommendationUserAffinity.Dimension.BRAND).exists()
    profile = RecommendationReplenishmentProfile.objects.get(user=user, product=p1)
    assert profile.orders_count == 1
