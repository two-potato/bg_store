from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views_public import (
    CheckInnView, MembershipRequestViewSet, DeliveryAddressViewSet,
    lookup_party_by_inn, lookup_bank_by_bik, lookup_party_preview, lookup_reverse_geocode,
)

router = DefaultRouter()
router.register("membership-requests", MembershipRequestViewSet, basename="membership-request")
router.register("delivery-addresses", DeliveryAddressViewSet, basename="delivery-address")

urlpatterns = [
    path("check-inn/", CheckInnView.as_view()),
    path("lookup/party/", lookup_party_by_inn),
    path("lookup/party_preview/", lookup_party_preview),
    path("lookup/revgeo/", lookup_reverse_geocode),
    path("lookup/bank/", lookup_bank_by_bik),
    path("", include(router.urls)),
]
