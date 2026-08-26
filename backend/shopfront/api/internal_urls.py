from __future__ import annotations

from django.urls import path

from .views_internal import (
    InternalRecommendationCartAPIView,
    InternalRecommendationCheckoutAPIView,
    InternalRecommendationHomeAPIView,
    InternalRecommendationProductAPIView,
    InternalRecommendationProductSectionAPIView,
    InternalRecommendationReorderAPIView,
    InternalRecommendationSearchRecoveryAPIView,
    InternalSearchQueryAPIView,
    InternalSearchSuggestionsAPIView,
)

urlpatterns = [
    path("search/query/", InternalSearchQueryAPIView.as_view(), name="internal_search_query"),
    path("search/suggestions/", InternalSearchSuggestionsAPIView.as_view(), name="internal_search_suggestions"),
    path("recommendations/home/", InternalRecommendationHomeAPIView.as_view(), name="internal_recommendations_home"),
    path(
        "recommendations/products/<int:product_id>/",
        InternalRecommendationProductAPIView.as_view(),
        name="internal_recommendations_product",
    ),
    path(
        "recommendations/products/<int:product_id>/sections/<slug:section>/",
        InternalRecommendationProductSectionAPIView.as_view(),
        name="internal_recommendations_product_section",
    ),
    path("recommendations/cart/", InternalRecommendationCartAPIView.as_view(), name="internal_recommendations_cart"),
    path("recommendations/checkout/", InternalRecommendationCheckoutAPIView.as_view(), name="internal_recommendations_checkout"),
    path("recommendations/reorder/", InternalRecommendationReorderAPIView.as_view(), name="internal_recommendations_reorder"),
    path(
        "recommendations/search-recovery/",
        InternalRecommendationSearchRecoveryAPIView.as_view(),
        name="internal_recommendations_search_recovery",
    ),
]

