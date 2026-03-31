import logging

from django.conf import settings
from django.db.models import Case, Count, IntegerField, Q, When
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import permissions, viewsets
from rest_framework.response import Response

from core.logging_utils import LoggedViewSetMixin

from shopfront.catalog_selectors import category_descendant_ids, category_slug_path
from shopfront.searching.service import DatabaseSearchProvider, get_search_provider

from ..models import Brand, Series, Category, Collection, Product
from ..serializers import BrandSerializer, SeriesSerializer, CategorySerializer, CollectionSerializer, ProductSerializer

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
    queryset = (
        Brand.objects.annotate(
            products_count=Count("products", distinct=True),
            categories_count=Count("products__category", distinct=True),
            collections_count=Count("products__collections", distinct=True),
        )
        .all()
        .order_by("name")
    )
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
    queryset = Category.objects.annotate(product_count=Count("products", distinct=True)).all().order_by("name")
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]


@extend_schema_view(
    list=extend_schema(
        tags=["Catalog"],
        summary="List collections",
        description="Возвращает публичный список активных коллекций и подборок каталога.",
        responses={200: CollectionSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["Catalog"],
        summary="Retrieve collection",
        description="Возвращает одну коллекцию каталога по id.",
        responses={200: CollectionSerializer},
    ),
)
@method_decorator(cache_page(getattr(settings, "CACHE_TTL_CATALOG_API", 120)), name="dispatch")
class CollectionViewSet(LoggedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = (
        Collection.objects.filter(is_active=True)
        .annotate(products_count=Count("products", distinct=True))
        .all()
        .order_by("-is_featured", "name")
    )
    serializer_class = CollectionSerializer
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
            OpenApiParameter(name="brand_slug", type=str, location=OpenApiParameter.QUERY, description="Slug бренда"),
            OpenApiParameter(name="series", type=int, location=OpenApiParameter.QUERY, description="ID серии"),
            OpenApiParameter(name="category", type=int, location=OpenApiParameter.QUERY, description="ID категории"),
            OpenApiParameter(name="category_path", type=str, location=OpenApiParameter.QUERY, description="Полный slug path категории"),
            OpenApiParameter(name="include_descendants", type=bool, location=OpenApiParameter.QUERY, description="Включить подкатегории для category/category_path"),
            OpenApiParameter(name="collection", type=int, location=OpenApiParameter.QUERY, description="ID коллекции"),
            OpenApiParameter(name="collection_slug", type=str, location=OpenApiParameter.QUERY, description="Slug коллекции"),
            OpenApiParameter(name="slug", type=str, location=OpenApiParameter.QUERY, description="Slug товара"),
            OpenApiParameter(name="q", type=str, location=OpenApiParameter.QUERY, description="Поисковый запрос для discovery и search surfaces"),
            OpenApiParameter(name="is_new", type=bool, location=OpenApiParameter.QUERY, description="Фильтр по новинкам"),
            OpenApiParameter(name="is_promo", type=bool, location=OpenApiParameter.QUERY, description="Фильтр по промо-товарам"),
            OpenApiParameter(name="limit", type=int, location=OpenApiParameter.QUERY, description="Ограничить размер ответа"),
            OpenApiParameter(name="offset", type=int, location=OpenApiParameter.QUERY, description="Сместить начало выдачи"),
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
    filterset_fields = ["brand", "series", "category", "slug", "is_new", "is_promo"]

    @staticmethod
    def _parse_int(value, *, minimum=0, maximum=None):
        if value in (None, ""):
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        if parsed < minimum:
            return None
        if maximum is not None:
            parsed = min(parsed, maximum)
        return parsed

    @staticmethod
    def _parse_bool(value):
        if value in (None, ""):
            return None
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return None

    @staticmethod
    def _resolve_category_by_path(category_path: str):
        normalized = "/".join(part for part in str(category_path or "").strip("/").split("/") if part)
        if not normalized:
            return None
        categories = list(Category.objects.only("id", "slug", "parent_id").order_by("parent_id", "id"))
        by_id = {category.id: category for category in categories}
        for category in categories:
            if category_slug_path(category, by_id) == normalized:
                return category
        return None

    def _search_product_ids(self, query: str, desired_size: int):
        provider = get_search_provider(prefer_semantic=True)
        try:
            bundle = provider.live_bundle(query=query, limit=desired_size, country_limit=0)
        except Exception as exc:
            log.warning("catalog_product_search_provider_failed", extra={"query": query, "reason": str(exc)})
            bundle = DatabaseSearchProvider().live_bundle(query=query, limit=desired_size, country_limit=0)
        if getattr(bundle, "provider", "") != DatabaseSearchProvider.code:
            db_bundle = DatabaseSearchProvider().live_bundle(query=query, limit=desired_size, country_limit=0)
            merged_ids = []
            seen_ids = set()
            for product_id in db_bundle.product_ids + bundle.product_ids:
                if product_id in seen_ids:
                    continue
                seen_ids.add(product_id)
                merged_ids.append(product_id)
                if len(merged_ids) >= desired_size:
                    break
            if merged_ids:
                bundle.product_ids = merged_ids
            merged_suggestions = []
            seen_suggestions = set()
            for suggestion in db_bundle.suggestions + bundle.suggestions:
                key = str(suggestion or "").strip().casefold()
                if not key or key in seen_suggestions:
                    continue
                seen_suggestions.add(key)
                merged_suggestions.append(str(suggestion).strip())
                if len(merged_suggestions) >= desired_size:
                    break
            if merged_suggestions:
                bundle.suggestions = merged_suggestions
        self._search_bundle = bundle
        return bundle.product_ids

    @staticmethod
    def _fresh_query_match_ids(qs, query: str, desired_size: int):
        query_filter = (
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(manufacturer_sku__icontains=query)
            | Q(barcode__icontains=query)
            | Q(brand__name__icontains=query)
            | Q(series__name__icontains=query)
            | Q(category__name__icontains=query)
        )
        return list(
            qs.filter(query_filter)
            .distinct()
            .order_by("-id")
            .values_list("id", flat=True)[:desired_size]
        )

    def _filter_queryset(self, qs):
        qp = self.request.query_params

        brand_id = self._parse_int(qp.get("brand"), minimum=1)
        if brand_id is not None:
            qs = qs.filter(brand_id=brand_id)

        brand_slug = (qp.get("brand_slug") or "").strip()
        if brand_slug:
            qs = qs.filter(brand__slug=brand_slug)

        series_id = self._parse_int(qp.get("series"), minimum=1)
        if series_id is not None:
            qs = qs.filter(series_id=series_id)

        slug = (qp.get("slug") or "").strip()
        if slug:
            qs = qs.filter(slug=slug)

        collection_id = self._parse_int(qp.get("collection"), minimum=1)
        if collection_id is not None:
            qs = qs.filter(collections__id=collection_id)

        collection_slug = (qp.get("collection_slug") or "").strip()
        if collection_slug:
            qs = qs.filter(collections__slug=collection_slug)

        category_id = self._parse_int(qp.get("category"), minimum=1)
        category_path = (qp.get("category_path") or "").strip()
        include_descendants = bool(self._parse_bool(qp.get("include_descendants")))

        resolved_category = None
        if category_path:
            resolved_category = self._resolve_category_by_path(category_path)
        elif category_id is not None:
            resolved_category = Category.objects.filter(id=category_id).only("id").first()

        if resolved_category is not None:
            category_ids = [resolved_category.id]
            if include_descendants:
                category_ids = category_descendant_ids(resolved_category)
            qs = qs.filter(category_id__in=category_ids)
        elif category_id is not None:
            qs = qs.filter(category_id=category_id)

        is_new = self._parse_bool(qp.get("is_new"))
        if is_new is not None:
            qs = qs.filter(is_new=is_new)

        is_promo = self._parse_bool(qp.get("is_promo"))
        if is_promo is not None:
            qs = qs.filter(is_promo=is_promo)

        query = " ".join((qp.get("q") or "").strip().split())
        if query:
            offset = self._parse_int(qp.get("offset"), minimum=0, maximum=10000) or 0
            limit = self._parse_int(qp.get("limit"), minimum=1, maximum=96) or 24
            desired_size = min(max(offset + limit + 120, 160), 400)
            provider_ids = self._search_product_ids(query, desired_size)
            fresh_ids = self._fresh_query_match_ids(qs, query, desired_size)
            ids = []
            seen_ids = set()
            for product_id in fresh_ids + provider_ids:
                if product_id in seen_ids:
                    continue
                seen_ids.add(product_id)
                ids.append(product_id)
                if len(ids) >= desired_size:
                    break
            if not ids:
                return qs.none()
            order_case = Case(
                *[When(id=product_id, then=position) for position, product_id in enumerate(ids)],
                default=len(ids),
                output_field=IntegerField(),
            )
            qs = qs.filter(id__in=ids).annotate(_search_rank=order_case).order_by("_search_rank", "-is_new", "name")
        else:
            qs = qs.order_by("-is_new", "name")

        return qs.distinct()

    def get_queryset(self):
        qs = super().get_queryset()
        qp = self.request.query_params
        filters = {k: qp.get(k) for k in self.filterset_fields if qp.get(k) not in (None, "")}
        for key in ("brand_slug", "category_path", "include_descendants", "collection", "collection_slug", "q"):
            if qp.get(key) not in (None, ""):
                filters[key] = qp.get(key)
        limit = self._parse_int(qp.get("limit"), minimum=1, maximum=96)
        offset = self._parse_int(qp.get("offset"), minimum=0, maximum=10000)
        if limit is not None:
            filters["limit"] = limit
        if offset is not None:
            filters["offset"] = offset
        if filters:
            log.info("catalog_product_list_filters", extra={"filters": filters})
        return self._filter_queryset(qs)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        limit = self._parse_int(request.query_params.get("limit"), minimum=1, maximum=96)
        offset = self._parse_int(request.query_params.get("offset"), minimum=0, maximum=10000) or 0

        if offset:
            queryset = queryset[offset:]
        if limit is not None:
            queryset = queryset[:limit]

        serializer = self.get_serializer(queryset, many=True)
        response = Response(serializer.data)
        if limit is not None:
            response["X-Servio-Limit"] = str(limit)
        if offset:
            response["X-Servio-Offset"] = str(offset)
        search_bundle = getattr(self, "_search_bundle", None)
        if search_bundle is not None:
            response["X-Servio-Search-Provider"] = str(getattr(search_bundle, "provider", "unknown"))
            if getattr(search_bundle, "effective_query", ""):
                response["X-Servio-Search-Effective-Query"] = str(search_bundle.effective_query)
            if getattr(search_bundle, "rewritten_query", ""):
                response["X-Servio-Search-Rewritten-Query"] = str(search_bundle.rewritten_query)
        return response
