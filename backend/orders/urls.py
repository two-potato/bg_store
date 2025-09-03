from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, OrderApproveView, OrderRejectView

router = DefaultRouter()
router.register("", OrderViewSet, basename="order")

urlpatterns = [
    path("", include(router.urls)),
    path("<int:pk>/approve/", OrderApproveView.as_view()),
    path("<int:pk>/reject/",  OrderRejectView.as_view()),
]
