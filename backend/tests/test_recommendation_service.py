import json

import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware

from catalog.models import Brand, Category, Product
from orders.models import Order, OrderItem
from shopfront.models import (
    BrandSubscription,
    FavoriteProduct,
    RecommendationProductAffinity,
    RecommendationSet,
    RecentlyViewedProduct,
)
from shopfront.recommendation_policy import remember_recommendation_dismiss
from shopfront.recommendation_service import (
    cart_recommendations,
    home_recommendations_context,
    product_detail_recommendations,
    product_section_context,
    reorder_recommendations,
)
from shopfront.models import RecommendationPopularitySnapshot


pytestmark = pytest.mark.django_db


def _make_product(*, seller, brand, category, sku: str, name: str, price: str = "100.00", stock_qty: int = 10, is_promo: bool = False):
    return Product.objects.create(
        seller=seller,
        brand=brand,
        category=category,
        sku=sku,
        name=name,
        price=price,
        stock_qty=stock_qty,
        is_promo=is_promo,
    )


def _request_with_session():
    from django.test import RequestFactory

    request = RequestFactory().get("/")
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()
    request.user = AnonymousUser()
    return request


def test_home_recommendations_context_uses_materialized_and_personalized_data(user):
    seller = get_user_model().objects.create_user(username="seller_rec", password="pass")
    brand = Brand.objects.create(name="Brand A")
    category = Category.objects.create(name="Category A")
    p1 = _make_product(seller=seller, brand=brand, category=category, sku="11110001", name="Espresso Beans")
    p2 = _make_product(seller=seller, brand=brand, category=category, sku="11110002", name="Arabica Roast", is_promo=True)
    FavoriteProduct.objects.create(user=user, product=p1)
    RecentlyViewedProduct.objects.create(user=user, product=p1)
    BrandSubscription.objects.create(user=user, brand=brand)
    RecommendationSet.objects.create(
        kind="personalized_home",
        scope_type=RecommendationSet.ScopeType.USER,
        scope_id=user.id,
        source="test",
        product_ids=[p2.id, p1.id],
    )

    ctx = home_recommendations_context(user, limit=8)

    assert [product.id for product in ctx["recommended_for_you"]] == [p2.id, p1.id]
    payload = json.loads(ctx["recommended_for_you_tracking_payload"])
    assert payload["event"] == "recommendation_impression"
    assert payload["surface"] == "home"
    assert payload["strategy"] == "materialized_or_ranked"
    assert payload["model_version"] == "heuristic_ltr_prep_v1"
    assert payload["ecommerce"]["items"][0]["recommendation_reason_codes"]


def test_product_section_context_prefers_affinity_records(user):
    seller = get_user_model().objects.create_user(username="seller_rec_2", password="pass")
    brand = Brand.objects.create(name="Brand B")
    category = Category.objects.create(name="Category B")
    source = _make_product(seller=seller, brand=brand, category=category, sku="11110011", name="Source")
    target = _make_product(seller=seller, brand=brand, category=category, sku="11110012", name="Target")
    RecommendationProductAffinity.objects.create(
        source_product=source,
        target_product=target,
        affinity_type=RecommendationProductAffinity.AffinityType.CO_PURCHASE,
        score="5.0000",
        orders_count=3,
    )

    ctx = product_section_context(source, "fbt", user=user)

    assert [product.id for product in ctx["products"]] == [target.id]
    assert ctx["recommendation_source"] == "product_frequently_bought_together"


def test_cart_and_reorder_recommendations_return_products(user):
    seller = get_user_model().objects.create_user(username="seller_rec_3", password="pass")
    brand = Brand.objects.create(name="Brand C")
    category = Category.objects.create(name="Category C")
    p1 = _make_product(seller=seller, brand=brand, category=category, sku="11110021", name="Cart Seed")
    p2 = _make_product(seller=seller, brand=brand, category=category, sku="11110022", name="Cart Upsell", is_promo=True)
    order = Order.objects.create(placed_by=user, customer_type=Order.CustomerType.COMPANY)
    OrderItem.objects.create(order=order, product=p2, name=p2.name, price=p2.price, qty=2)

    cart_ctx = cart_recommendations([p1], user=user, limit=8)
    reorder = reorder_recommendations(user, limit=8)

    assert [product.id for product in cart_ctx["products"]] == [p2.id]
    assert [product.id for product in reorder] == [p2.id]


def test_product_detail_recommendations_include_similarity_fallback(user):
    seller = get_user_model().objects.create_user(username="seller_rec_4", password="pass")
    brand = Brand.objects.create(name="Brand D")
    category = Category.objects.create(name="Category D")
    p1 = _make_product(seller=seller, brand=brand, category=category, sku="11110031", name="Bar Syrup Vanilla", is_promo=True)
    p2 = _make_product(seller=seller, brand=brand, category=category, sku="11110032", name="Bar Syrup Caramel")
    RecommendationProductAffinity.objects.create(
        source_product=p1,
        target_product=p2,
        affinity_type=RecommendationProductAffinity.AffinityType.SIMILAR,
        score="3.0000",
        orders_count=2,
    )

    ctx = product_detail_recommendations(p1, user=user, limit=12)

    assert p2.id in [product.id for product in ctx["similar_products"]]


def test_home_recommendations_context_uses_session_cold_start_for_guest(db):
    seller = get_user_model().objects.create_user(username="seller_guest_rec", password="pass")
    brand = Brand.objects.create(name="Brand Session")
    category = Category.objects.create(name="Category Session")
    viewed = _make_product(seller=seller, brand=brand, category=category, sku="11110991", name="Viewed seed")
    recommended = _make_product(seller=seller, brand=brand, category=category, sku="11110992", name="Category hot", is_promo=True)
    RecommendationPopularitySnapshot.objects.create(
        scope_type=RecommendationPopularitySnapshot.ScopeType.CATEGORY,
        scope_id=category.id,
        window="7d",
        product=recommended,
        score="9.0000",
    )
    RecommendationPopularitySnapshot.objects.create(
        scope_type=RecommendationPopularitySnapshot.ScopeType.GLOBAL,
        scope_id=0,
        window="7d",
        product=recommended,
        score="7.0000",
    )
    request = _request_with_session()
    request.session["recently_viewed_products"] = [viewed.id]
    request.session.save()

    ctx = home_recommendations_context(request.user, request=request, limit=8)

    assert [product.id for product in ctx["home_recently_viewed"]] == [viewed.id]
    assert recommended.id in [product.id for product in ctx["recommended_for_you"]]
    payload = json.loads(ctx["recommended_for_you_tracking_payload"])
    assert payload["strategy"] == "cold_start_ranked"


def test_home_recommendations_context_excludes_dismissed_products(db):
    seller = get_user_model().objects.create_user(username="seller_dismiss_rec", password="pass")
    brand = Brand.objects.create(name="Brand Dismiss")
    category = Category.objects.create(name="Category Dismiss")
    p1 = _make_product(seller=seller, brand=brand, category=category, sku="11110993", name="Dismiss me", is_promo=True)
    p2 = _make_product(seller=seller, brand=brand, category=category, sku="11110994", name="Keep me")
    RecommendationPopularitySnapshot.objects.create(
        scope_type=RecommendationPopularitySnapshot.ScopeType.GLOBAL,
        scope_id=0,
        window="7d",
        product=p1,
        score="10.0000",
    )
    RecommendationPopularitySnapshot.objects.create(
        scope_type=RecommendationPopularitySnapshot.ScopeType.GLOBAL,
        scope_id=0,
        window="7d",
        product=p2,
        score="9.0000",
    )
    request = _request_with_session()
    remember_recommendation_dismiss(request, surface="home", product_id=p1.id)

    ctx = home_recommendations_context(request.user, request=request, limit=8)

    recommended_ids = [product.id for product in ctx["recommended_for_you"]]
    assert p1.id not in recommended_ids
    assert p2.id in recommended_ids
