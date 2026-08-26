from __future__ import annotations

from django.urls import path

from .views import SearchQueryAPIView, SearchSuggestionsAPIView

urlpatterns = [
    path("search/query/", SearchQueryAPIView.as_view(), name="api_search_query"),
    path("search/suggestions/", SearchSuggestionsAPIView.as_view(), name="api_search_suggestions"),
]
