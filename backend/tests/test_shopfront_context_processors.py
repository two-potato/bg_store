from django.core.cache import cache
from django.test import RequestFactory
from django.template import Context, Template

from catalog.models import Brand, Category, Product
from shopfront.request_state import favorite_product_ids_for_user
from shopfront.context_processors import favorites_state, invalidate_favorites_state
from shopfront.models import FavoriteProduct


def test_favorites_state_uses_cache_until_invalidated(user, db):
    brand = Brand.objects.create(name="FavBrand")
    category = Category.objects.create(name="FavCategory")
    product = Product.objects.create(
        sku="12345678",
        name="Favorite Cache Product",
        brand=brand,
        category=category,
        price=10,
        stock_qty=5,
    )
    request = RequestFactory().get("/")
    request.user = user
    cache.clear()

    assert favorites_state(request) == {}
    assert favorite_product_ids_for_user(user) == []

    FavoriteProduct.objects.create(user=user, product=product)
    # Cached state should remain stale until explicit invalidation.
    assert favorites_state(request) == {}
    assert favorite_product_ids_for_user(user) == []

    invalidate_favorites_state(user.id)
    assert favorites_state(request) == {}
    assert favorite_product_ids_for_user(user) == [product.id]


def test_shopfront_state_template_tags_use_request_scoped_state(user, db):
    brand = Brand.objects.create(name="TagBrand")
    category = Category.objects.create(name="TagCategory")
    product = Product.objects.create(
        sku="87654321",
        name="Tagged Product",
        brand=brand,
        category=category,
        price=12,
        stock_qty=9,
    )
    FavoriteProduct.objects.create(user=user, product=product)

    request = RequestFactory().get("/")
    request.user = user
    request.session = {"cart": {str(product.id): {"qty": 3}}}
    cache.clear()
    invalidate_favorites_state(user.id)

    rendered = Template(
        "{% load shopfront_state %}"
        "{% cart_quantity request product.id as qty %}"
        "{% product_in_cart request product.id as in_cart %}"
        "{% product_favorited request product.id as favorited %}"
        "{{ qty }}|{{ in_cart }}|{{ favorited }}"
    ).render(Context({"request": request, "product": product}))

    assert rendered == "3|True|True"
