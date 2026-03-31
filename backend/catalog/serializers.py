from rest_framework import serializers
from drf_spectacular.utils import OpenApiExample, extend_schema_serializer
from .models import Brand, Series, Category, Collection, Product, ProductImage, Tag, Color, Country, normalize_public_media_url


@extend_schema_serializer(
    examples=[OpenApiExample("Brand", value={"id": 1, "name": "Complaex Signature", "slug": "complaex-signature"}, response_only=True)]
)
class BrandSerializer(serializers.ModelSerializer):
    photo = serializers.SerializerMethodField()
    products_count = serializers.IntegerField(read_only=True)
    categories_count = serializers.IntegerField(read_only=True)
    collections_count = serializers.IntegerField(read_only=True)

    def get_photo(self, obj):
        photo = getattr(obj, "photo", None)
        if not photo:
            return ""
        return normalize_public_media_url(getattr(photo, "url", ""))

    class Meta:
        model = Brand
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "landing_body",
            "faq_title",
            "faq_body",
            "meta_title",
            "meta_description",
            "photo",
            "products_count",
            "categories_count",
            "collections_count",
        ]

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
    photo = serializers.SerializerMethodField()
    full_slug_path = serializers.CharField(read_only=True)
    product_count = serializers.IntegerField(read_only=True)

    def get_photo(self, obj):
        photo = getattr(obj, "photo", None)
        if not photo:
            return ""
        return normalize_public_media_url(getattr(photo, "url", ""))

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "parent",
            "description",
            "hero_title",
            "hero_text",
            "landing_body",
            "faq_title",
            "faq_body",
            "meta_title",
            "meta_description",
            "photo",
            "full_slug_path",
            "product_count",
        ]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Collection",
            value={
                "id": 1,
                "name": "Открытие бара",
                "slug": "bar-launch-kit",
                "description": "Кураторская подборка для запуска барного направления.",
                "hero_title": "Открытие бара",
                "hero_text": "Сценарная подборка под запуск и repeat purchase.",
                "landing_body": "Подборка собрана под базовые закупочные сценарии.",
                "faq_title": "FAQ по подборке",
                "faq_body": "Ответы на частые вопросы по составу коллекции.",
                "meta_title": "Коллекция Открытие бара — Servio",
                "meta_description": "Кураторская подборка товаров Servio.",
                "photo": "/media/collection_photos/bar-launch.jpg",
                "is_active": True,
                "is_featured": True,
                "products_count": 18,
            },
            response_only=True,
        )
    ]
)
class CollectionSerializer(serializers.ModelSerializer):
    photo = serializers.SerializerMethodField()
    products_count = serializers.IntegerField(read_only=True)

    def get_photo(self, obj):
        photo = getattr(obj, "photo", None)
        if not photo:
            return ""
        return normalize_public_media_url(getattr(photo, "url", ""))

    class Meta:
        model = Collection
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "hero_title",
            "hero_text",
            "landing_body",
            "faq_title",
            "faq_body",
            "meta_title",
            "meta_description",
            "photo",
            "is_active",
            "is_featured",
            "products_count",
        ]

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
    category_detail = CategorySerializer(source="category", read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    # Keep backward-compatible representation: expose names for FKs
    color = serializers.SlugRelatedField(read_only=True, slug_field="name", help_text="Название цвета товара")
    country_of_origin = serializers.SlugRelatedField(read_only=True, slug_field="name", help_text="Страна происхождения")
    seller = serializers.SlugRelatedField(read_only=True, slug_field="username", help_text="Username продавца")
    class Meta:
        model = Product
        fields = ["id","sku","slug","manufacturer_sku","name","brand","series","category","category_detail",
                  "country_of_origin","material","purpose","color",
                  "diameter_mm","height_mm","length_mm","width_mm","volume_ml","weight_g",
                  "pack_qty","unit","barcode","price","stock_qty","min_order_qty","lead_time_days",
                  "is_new","is_promo","flavor","composition","shelf_life","description",
                  "attributes","images","tags","seller"]
