from __future__ import annotations

from shopfront.api.views_search import SearchQueryAPIView as LegacySearchQueryAPIView
from shopfront.api.views_search import SearchSuggestionsAPIView as LegacySearchSuggestionsAPIView


class SearchQueryAPIView(LegacySearchQueryAPIView):
    """Stable public search endpoint while execution moves out of shopfront."""


class SearchSuggestionsAPIView(LegacySearchSuggestionsAPIView):
    """Stable public suggestions endpoint while execution moves out of shopfront."""
