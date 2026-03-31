from __future__ import annotations

from django.urls import path

from .views_recommendations import (
    RecommendationCartAPIView,
    RecommendationCheckoutAPIView,
    RecommendationHomeAPIView,
    RecommendationProductAPIView,
    RecommendationProductSectionAPIView,
    RecommendationReorderAPIView,
    RecommendationSearchRecoveryAPIView,
)
from .views_search import SearchQueryAPIView, SearchSuggestionsAPIView

urlpatterns = [
    path("search/query/", SearchQueryAPIView.as_view(), name="api_search_query"),
    path("search/suggestions/", SearchSuggestionsAPIView.as_view(), name="api_search_suggestions"),
    path("recommendations/home/", RecommendationHomeAPIView.as_view(), name="api_recommendations_home"),
    path("recommendations/products/<int:product_id>/", RecommendationProductAPIView.as_view(), name="api_recommendations_product"),
    path(
        "recommendations/products/<int:product_id>/sections/<slug:section>/",
        RecommendationProductSectionAPIView.as_view(),
        name="api_recommendations_product_section",
    ),
    path("recommendations/cart/", RecommendationCartAPIView.as_view(), name="api_recommendations_cart"),
    path("recommendations/checkout/", RecommendationCheckoutAPIView.as_view(), name="api_recommendations_checkout"),
    path("recommendations/reorder/", RecommendationReorderAPIView.as_view(), name="api_recommendations_reorder"),
    path("recommendations/search-recovery/", RecommendationSearchRecoveryAPIView.as_view(), name="api_recommendations_search_recovery"),
]

