import pytest
from django.core.exceptions import ValidationError
from catalog.models import Product, ProductImage, Brand, Category, Color, Country
from users.models import Friendship
from django.contrib.auth import get_user_model
from catalog.serializers import ProductSerializer

pytestmark = pytest.mark.django_db


def _base_product():
    b, _ = Brand.objects.get_or_create(name="B1")
    c, _ = Category.objects.get_or_create(name="C1")
    return b, c


def test_product_sku_must_be_8_digits():
    b, c = _base_product()
    # valid
    p = Product.objects.create(sku="12345678", name="N", brand=b, category=c)
    assert p.sku == "12345678"
    # invalid (non-digit)
    with pytest.raises(ValidationError):
        p2 = Product(sku="ABC12345", name="X", brand=b, category=c)
        p2.full_clean()
    # invalid (length)
    with pytest.raises(ValidationError):
        p3 = Product(sku="1234567", name="Y", brand=b, category=c)
        p3.full_clean()


def test_product_image_limit_10():
    b, c = _base_product()
    p = Product.objects.create(sku="87654321", name="N2", brand=b, category=c)
    for i in range(10):
        ProductImage.objects.create(product=p, url=f"https://example.com/{i}.jpg", ordering=i)
    # 11th should fail
    with pytest.raises(ValidationError):
        ProductImage.objects.create(product=p, url="https://example.com/11.jpg", ordering=11)


def test_friendship_unique_and_str():
    U = get_user_model()
    u1 = U.objects.create_user(username="u1")
    u2 = U.objects.create_user(username="u2")
    f = Friendship.objects.create(from_user=u1, to_user=u2)
    assert "pending" in str(f)
    f.accepted = True
    f.save()
    assert "accepted" in str(f)
    with pytest.raises(Exception):
        Friendship.objects.create(from_user=u1, to_user=u2)


def test_product_serializer_color_country_names():
    b, c = _base_product()
    color = Color.objects.create(name="Чёрный")
    country = Country.objects.create(name="Россия", iso_code="RUS")
    p = Product.objects.create(sku="11223344", name="S", brand=b, category=c, color=color, country_of_origin=country)
    data = ProductSerializer(p).data
    assert data["color"] == "Чёрный"
    assert data["country_of_origin"] == "Россия"
