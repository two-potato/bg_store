from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BrandViewSet, SeriesViewSet, CategoryViewSet, ProductViewSet

router = DefaultRouter()
router.register("brands", BrandViewSet)
router.register("series", SeriesViewSet)
router.register("categories", CategoryViewSet)
router.register("products", ProductViewSet)

urlpatterns = [ path("", include(router.urls)) ]
