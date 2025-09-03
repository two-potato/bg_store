from rest_framework import viewsets, permissions
from core.logging_utils import LoggedViewSetMixin
from django_filters.rest_framework import DjangoFilterBackend
from .models import Brand, Series, Category, Product
from .serializers import BrandSerializer, SeriesSerializer, CategorySerializer, ProductSerializer

class BrandViewSet(LoggedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Brand.objects.all().order_by("name")
    serializer_class = BrandSerializer
    permission_classes = [permissions.AllowAny]

class SeriesViewSet(LoggedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Series.objects.select_related("brand").all().order_by("brand__name","name")
    serializer_class = SeriesSerializer
    permission_classes = [permissions.AllowAny]

class CategoryViewSet(LoggedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

class ProductViewSet(LoggedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.select_related("brand","series","category").prefetch_related("images").all().order_by("-is_new","name")
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["brand","series","category","is_new","is_promo"]
