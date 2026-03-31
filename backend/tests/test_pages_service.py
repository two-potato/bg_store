import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from catalog.models import Brand, Category, Collection, CollectionItem, Product
from shopfront.models import BrandSubscription
from shopfront.pages_service import (
    BrandDetailService,
    CategoryDetailService,
    CollectionDetailService,
)


pytestmark = pytest.mark.django_db


def _request(path: str, user) -> object:
    request = RequestFactory().get(path)
    request.user = user
    return request


def test_brand_detail_service_builds_context_with_subscription(user):
    brand = Brand.objects.create(name="Service Brand", description="Brand description")
    category = Category.objects.create(name="Service Category", slug="service-category")
    product = Product.objects.create(
        sku="77889900",
        name="Service Product",
        brand=brand,
        category=category,
        price=120,
        stock_qty=5,
    )
    collection = Collection.objects.create(name="Service Collection", is_active=True, is_featured=True)
    CollectionItem.objects.create(collection=collection, product=product, ordering=1)
    BrandSubscription.objects.create(user=user, brand=brand)

    context = BrandDetailService(_request(f"/brands/{brand.slug}/", user)).build_context(brand.slug)

    assert context is not None
    assert context.brand.id == brand.id
    assert context.is_brand_subscribed is True
    assert [p.id for p in context.products] == [product.id]
    assert context.featured_collections
    assert "seo_title" in context.seo_context


def test_category_detail_service_builds_context_for_nested_path():
    parent = Category.objects.create(name="Parent Category", slug="parent-category")
    child = Category.objects.create(name="Child Category", slug="child-category", parent=parent)
    brand = Brand.objects.create(name="Nested Brand")
    product = Product.objects.create(
        sku="77889901",
        name="Nested Product",
        brand=brand,
        category=child,
        price=130,
        stock_qty=6,
    )

    context = CategoryDetailService(
        _request("/catalog/parent-category/child-category/", AnonymousUser())
    ).build_context(
        f"{parent.slug}/{child.slug}"
    )

    assert context is not None
    assert context.category.id == child.id
    assert [p.id for p in context.products] == [product.id]
    assert context.breadcrumbs
    assert context.featured_brands
    assert "seo_description" in context.seo_context


def test_category_detail_service_returns_none_for_invalid_path():
    service = CategoryDetailService(_request("/catalog/missing/", AnonymousUser()))
    assert service.build_context("missing/path") is None


def test_collection_detail_service_builds_context_and_handles_missing(user):
    brand = Brand.objects.create(name="Collection Brand")
    category = Category.objects.create(name="Collection Category", slug="collection-category")
    product = Product.objects.create(
        sku="77889902",
        name="Collection Product",
        brand=brand,
        category=category,
        price=140,
        stock_qty=7,
    )
    main = Collection.objects.create(name="Main Collection", is_active=True, is_featured=True)
    CollectionItem.objects.create(collection=main, product=product, ordering=1)
    Collection.objects.create(name="Related Collection", is_active=True, is_featured=True)

    service = CollectionDetailService(_request(f"/collections/{main.slug}/", user))
    context = service.build_context(main.slug)

    assert context is not None
    assert context.collection.id == main.id
    assert [p.id for p in context.products] == [product.id]
    assert context.related_collections
    assert service.build_context("missing-collection") is None
