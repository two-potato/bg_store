from rest_framework import viewsets, permissions
from core.logging_utils import LoggedViewSetMixin
from django_filters.rest_framework import DjangoFilterBackend
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
import logging
from ..models import Brand, Series, Category, Product
from ..serializers import BrandSerializer, SeriesSerializer, CategorySerializer, ProductSerializer

log = logging.getLogger("catalog")


@extend_schema_view(
    list=extend_schema(
        tags=["Catalog"],
        summary="List brands",
        description="Возвращает публичный список брендов каталога. Доступен без авторизации.",
        responses={200: BrandSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["Catalog"],
        summary="Retrieve brand",
        description="Возвращает один бренд каталога по id.",
        responses={200: BrandSerializer},
    ),
)
@method_decorator(cache_page(getattr(settings, "CACHE_TTL_CATALOG_API", 120)), name="dispatch")
class BrandViewSet(LoggedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Brand.objects.all().order_by("name")
    serializer_class = BrandSerializer
    permission_classes = [permissions.AllowAny]

@extend_schema_view(
    list=extend_schema(
        tags=["Catalog"],
        summary="List series",
        description="Возвращает товарные серии с вложенной информацией о бренде.",
        responses={200: SeriesSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["Catalog"],
        summary="Retrieve series",
        description="Возвращает одну серию каталога по id.",
        responses={200: SeriesSerializer},
    ),
)
@method_decorator(cache_page(getattr(settings, "CACHE_TTL_CATALOG_API", 120)), name="dispatch")
class SeriesViewSet(LoggedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Series.objects.select_related("brand").all().order_by("brand__name","name")
    serializer_class = SeriesSerializer
    permission_classes = [permissions.AllowAny]

@extend_schema_view(
    list=extend_schema(
        tags=["Catalog"],
        summary="List categories",
        description="Возвращает список категорий каталога. Для дочерних категорий поле `parent` содержит id родителя.",
        responses={200: CategorySerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["Catalog"],
        summary="Retrieve category",
        description="Возвращает одну категорию каталога по id.",
        responses={200: CategorySerializer},
    ),
)
@method_decorator(cache_page(getattr(settings, "CACHE_TTL_CATALOG_API", 120)), name="dispatch")
class CategoryViewSet(LoggedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

@extend_schema_view(
    list=extend_schema(
        tags=["Catalog"],
        summary="List products",
        description=(
            "Публичный список товаров каталога. Поддерживает фильтрацию по бренду, серии, "
            "категории и промо-признакам."
        ),
        parameters=[
            OpenApiParameter(name="brand", type=int, location=OpenApiParameter.QUERY, description="ID бренда"),
            OpenApiParameter(name="series", type=int, location=OpenApiParameter.QUERY, description="ID серии"),
            OpenApiParameter(name="category", type=int, location=OpenApiParameter.QUERY, description="ID категории"),
            OpenApiParameter(name="is_new", type=bool, location=OpenApiParameter.QUERY, description="Фильтр по новинкам"),
            OpenApiParameter(name="is_promo", type=bool, location=OpenApiParameter.QUERY, description="Фильтр по промо-товарам"),
        ],
        responses={
            200: OpenApiResponse(
                response=ProductSerializer(many=True),
                examples=[
                    OpenApiExample(
                        "Product list sample",
                        value=[
                            {
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
                            }
                        ],
                        response_only=True,
                    )
                ],
            )
        },
    ),
    retrieve=extend_schema(
        tags=["Catalog"],
        summary="Retrieve product",
        description="Возвращает полную карточку товара каталога по id.",
        responses={200: ProductSerializer},
    ),
)
@method_decorator(cache_page(getattr(settings, "CACHE_TTL_CATALOG_API", 120)), name="dispatch")
class ProductViewSet(LoggedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.select_related("brand", "series", "category", "seller").prefetch_related("images").all().order_by("-is_new", "name")
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["brand","series","category","is_new","is_promo"]

    def get_queryset(self):
        qs = super().get_queryset()
        qp = self.request.query_params
        filters = {k: qp.get(k) for k in self.filterset_fields if qp.get(k) not in (None, "")}
        if filters:
            log.info("catalog_product_list_filters", extra={"filters": filters})
        return qs
