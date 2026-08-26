from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from shopfront.searching.contracts import search_query_contract, search_suggestions_contract

from .serializers import SearchQueryResponseSerializer, SearchSuggestionsResponseSerializer


def _limit(value: object, *, default: int, upper: int, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(upper, parsed))


class SearchQueryAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Search"],
        summary="Search query contract",
        description=(
            "Контракт storefront-поиска. Возвращает результаты, подсказки и фасеты в единой схеме. "
            "Работает через `django-inline` или внешний FastAPI search-service с fallback."
        ),
        parameters=[
            OpenApiParameter("q", str, OpenApiParameter.QUERY, required=True, description="Поисковый запрос"),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY, required=False, description="Лимит товаров (1..64)"),
            OpenApiParameter("country_limit", int, OpenApiParameter.QUERY, required=False, description="Лимит country suggestions"),
        ],
        responses={200: OpenApiResponse(response=SearchQueryResponseSerializer)},
    )
    def get(self, request):
        query = str(request.query_params.get("q") or "").strip()
        limit = _limit(request.query_params.get("limit"), default=24, upper=64)
        country_limit = _limit(request.query_params.get("country_limit"), default=6, upper=24, minimum=0)
        payload = search_query_contract(query=query, limit=limit, country_limit=country_limit, request=request)
        serializer = SearchQueryResponseSerializer(payload)
        return Response(serializer.data)


class SearchSuggestionsAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Search"],
        summary="Search suggestions contract",
        description="Контракт подсказок поиска (suggestions/corrections/country hints) с fallback на Django-провайдер.",
        parameters=[
            OpenApiParameter("q", str, OpenApiParameter.QUERY, required=True, description="Поисковый запрос"),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY, required=False, description="Лимит подсказок (1..32)"),
            OpenApiParameter("country_limit", int, OpenApiParameter.QUERY, required=False, description="Лимит country suggestions"),
        ],
        responses={200: OpenApiResponse(response=SearchSuggestionsResponseSerializer)},
    )
    def get(self, request):
        query = str(request.query_params.get("q") or "").strip()
        limit = _limit(request.query_params.get("limit"), default=10, upper=32)
        country_limit = _limit(request.query_params.get("country_limit"), default=6, upper=24, minimum=0)
        payload = search_suggestions_contract(query=query, limit=limit, country_limit=country_limit, request=request)
        serializer = SearchSuggestionsResponseSerializer(payload)
        return Response(serializer.data)
