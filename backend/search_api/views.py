from __future__ import annotations

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .gateway import query_contract, suggestions_contract


def _limit(value: object, *, default: int, upper: int, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(upper, parsed))


class SearchQueryAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        query = str(request.query_params.get("q") or "").strip()
        limit = _limit(request.query_params.get("limit"), default=24, upper=64)
        country_limit = _limit(request.query_params.get("country_limit"), default=6, upper=24, minimum=0)
        return Response(query_contract(query=query, limit=limit, country_limit=country_limit, request=request))


class SearchSuggestionsAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        query = str(request.query_params.get("q") or "").strip()
        limit = _limit(request.query_params.get("limit"), default=10, upper=32)
        country_limit = _limit(request.query_params.get("country_limit"), default=6, upper=24, minimum=0)
        return Response(suggestions_contract(query=query, limit=limit, country_limit=country_limit, request=request))
