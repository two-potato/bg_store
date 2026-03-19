from rest_framework import serializers
from drf_spectacular.utils import OpenApiExample, extend_schema_serializer
from .models import Brand, Series, Category, Product, ProductImage, Tag, Color, Country


@extend_schema_serializer(
    examples=[OpenApiExample("Brand", value={"id": 1, "name": "Complaex Signature"}, response_only=True)]
)
class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name"]

@extend_schema_serializer(
    examples=[OpenApiExample("Series", value={"id": 1, "name": "Night Shift", "brand": {"id": 1, "name": "Complaex Signature"}}, response_only=True)]
)
class SeriesSerializer(serializers.ModelSerializer):
    brand = BrandSerializer(read_only=True)

    class Meta:
        model = Series
        fields = ["id", "name", "brand"]

@extend_schema_serializer(
    examples=[OpenApiExample("Category", value={"id": 1, "name": "Посуда для подачи", "slug": "category-1", "parent": None}, response_only=True)]
)
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "parent"]

class ColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Color
        fields = ["id", "name", "hex_code"]

class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ["id", "name", "iso_code"]

@extend_schema_serializer(
    examples=[OpenApiExample("Product image", value={"url": "https://complaexbar.ru/media/products/10000001.png", "alt": "Тарелка для подачи", "is_primary": True, "ordering": 0}, response_only=True)]
)
class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["url", "alt", "is_primary", "ordering"]

@extend_schema_serializer(
    examples=[OpenApiExample("Tag", value={"id": 14, "name": "Для сервировки", "slug": "catalog-tag"}, response_only=True)]
)
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]

@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Product",
            value={
                "id": 1,
                "sku": "10000001",
                "slug": "night-shift-plate",
                "manufacturer_sku": "CBR-10000001",
                "name": "Тарелка для подачи Night Shift 21 см",
                "brand": {"id": 1, "name": "Complaex Signature"},
                "series": {"id": 1, "name": "Night Shift", "brand": {"id": 1, "name": "Complaex Signature"}},
                "category": 1,
                "country_of_origin": "Италия",
                "material": "фарфор",
                "purpose": "Для ежедневной работы направления «посуда для подачи»",
                "color": "Молочный",
                "diameter_mm": "210.00",
                "height_mm": "30.00",
                "length_mm": None,
                "width_mm": None,
                "volume_ml": "500.00",
                "weight_g": "620.00",
                "pack_qty": 6,
                "unit": "шт",
                "barcode": "460000010000001",
                "price": "790.00",
                "stock_qty": 24,
                "is_new": True,
                "is_promo": False,
                "flavor": "без вкусового акцента",
                "composition": "Рабочий материал: фарфор.",
                "shelf_life": "12 месяцев",
                "attributes": {"Проект": "complaexbar.ru"},
                "images": [{"url": "https://complaexbar.ru/media/products/10000001.png", "alt": "Тарелка", "is_primary": True, "ordering": 0}],
                "tags": [{"id": 1, "name": "Посуда для подачи", "slug": "catalog-tag"}],
                "seller": "horeca_manager",
            },
            response_only=True,
        )
    ]
)
class ProductSerializer(serializers.ModelSerializer):
    brand = BrandSerializer(read_only=True)
    series = SeriesSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    # Keep backward-compatible representation: expose names for FKs
    color = serializers.SlugRelatedField(read_only=True, slug_field="name", help_text="Название цвета товара")
    country_of_origin = serializers.SlugRelatedField(read_only=True, slug_field="name", help_text="Страна происхождения")
    seller = serializers.SlugRelatedField(read_only=True, slug_field="username", help_text="Username продавца")
    class Meta:
        model = Product
        fields = ["id","sku","slug","manufacturer_sku","name","brand","series","category",
                  "country_of_origin","material","purpose","color",
                  "diameter_mm","height_mm","length_mm","width_mm","volume_ml","weight_g",
                  "pack_qty","unit","barcode","price","stock_qty","is_new","is_promo",
                  "flavor","composition","shelf_life","attributes","images","tags","seller"]
