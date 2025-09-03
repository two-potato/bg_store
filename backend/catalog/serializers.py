from rest_framework import serializers
from .models import Brand, Series, Category, Product, ProductImage, Tag

class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name"]

class SeriesSerializer(serializers.ModelSerializer):
    brand = BrandSerializer(read_only=True)

    class Meta:
        model = Series
        fields = ["id", "name", "brand"]

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "parent"]

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["url", "alt", "is_primary", "ordering"]

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]

class ProductSerializer(serializers.ModelSerializer):
    brand = BrandSerializer(read_only=True)
    series = SeriesSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    class Meta:
        model = Product
        fields = ["id","sku","manufacturer_sku","name","brand","series","category",
                  "country_of_origin","material","purpose","color",
                  "diameter_mm","height_mm","length_mm","width_mm","volume_ml","weight_g",
                  "pack_qty","unit","barcode","price","stock_qty","is_new","is_promo",
                  "flavor","composition","shelf_life","attributes","images","tags"]
