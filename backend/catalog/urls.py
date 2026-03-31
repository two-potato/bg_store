from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.views import BrandViewSet, SeriesViewSet, CategoryViewSet, CollectionViewSet, ProductViewSet

router = DefaultRouter()
router.register("brands", BrandViewSet)
router.register("series", SeriesViewSet)
router.register("categories", CategoryViewSet)
router.register("collections", CollectionViewSet)
router.register("products", ProductViewSet)

urlpatterns = [ path("", include(router.urls)) ]
