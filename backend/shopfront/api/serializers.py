from __future__ import annotations

from rest_framework import serializers


class ProductCardSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    sku = serializers.CharField()
    name = serializers.CharField()
    image_url = serializers.CharField(allow_blank=True)
    price = serializers.CharField()
    stock_qty = serializers.IntegerField()
    min_order_qty = serializers.IntegerField()
    brand_name = serializers.CharField(allow_blank=True)
    seller_name = serializers.CharField(allow_blank=True)
    rating_avg = serializers.FloatField()
    rating_count = serializers.IntegerField()
    is_new = serializers.BooleanField()
    is_promo = serializers.BooleanField()


class SearchFacetOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()
    count = serializers.IntegerField()


class SearchFacetAvailabilitySerializer(serializers.Serializer):
    in_stock = serializers.IntegerField()
    out_of_stock = serializers.IntegerField()


class SearchFacetPriceSerializer(serializers.Serializer):
    min = serializers.CharField()
    max = serializers.CharField()


class SearchFacetsSerializer(serializers.Serializer):
    brands = SearchFacetOptionSerializer(many=True)
    categories = SearchFacetOptionSerializer(many=True)
    availability = SearchFacetAvailabilitySerializer()
    price = SearchFacetPriceSerializer()


class SearchQueryResponseSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    source = serializers.CharField()
    service_source = serializers.CharField(required=False, allow_blank=True)
    engine_source = serializers.CharField(required=False, allow_blank=True)
    query = serializers.CharField()
    effective_query = serializers.CharField(allow_blank=True)
    rewritten_query = serializers.CharField(allow_blank=True)
    rewrite_kind = serializers.CharField(allow_blank=True)
    provider = serializers.CharField()
    product_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)
    products = ProductCardSerializer(many=True)
    suggestions = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    corrections = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    countries = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    facets = SearchFacetsSerializer()
    service_error = serializers.CharField(required=False)


class SearchSuggestionsResponseSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    source = serializers.CharField()
    service_source = serializers.CharField(required=False, allow_blank=True)
    engine_source = serializers.CharField(required=False, allow_blank=True)
    query = serializers.CharField()
    provider = serializers.CharField()
    effective_query = serializers.CharField(allow_blank=True)
    rewritten_query = serializers.CharField(allow_blank=True)
    rewrite_kind = serializers.CharField(allow_blank=True)
    suggestions = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    corrections = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    countries = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    service_error = serializers.CharField(required=False)


class RecommendationSectionSerializer(serializers.Serializer):
    key = serializers.CharField()
    title = serializers.CharField()
    source = serializers.CharField(allow_blank=True)
    strategy = serializers.CharField(allow_blank=True)
    tracking_payload = serializers.CharField(allow_blank=True)
    impression_id = serializers.CharField(required=False, allow_blank=True)
    fallback_source = serializers.CharField(required=False, allow_blank=True)
    empty_reason = serializers.CharField(required=False, allow_blank=True)
    products = ProductCardSerializer(many=True)


class RecommendationResponseSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    source = serializers.CharField()
    recommendation_id = serializers.CharField(required=False, allow_blank=True)
    service_source = serializers.CharField(required=False, allow_blank=True)
    engine_source = serializers.CharField(required=False, allow_blank=True)
    fallback_source = serializers.CharField(required=False, allow_blank=True)
    empty_reason = serializers.CharField(required=False, allow_blank=True)
    latency_ms = serializers.IntegerField(required=False)
    surface = serializers.CharField()
    variant = serializers.CharField()
    sections = RecommendationSectionSerializer(many=True)
    service_error = serializers.CharField(required=False)
    error = serializers.CharField(required=False)


class RecommendationSeedRequestSerializer(serializers.Serializer):
    product_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=64,
    )
    limit = serializers.IntegerField(required=False, min_value=1, max_value=32, default=8)
