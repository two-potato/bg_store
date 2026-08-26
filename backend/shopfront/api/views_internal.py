from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from shopfront.recommendation.contracts import (
    recommendation_cart_contract,
    recommendation_home_contract,
    recommendation_product_contract,
    recommendation_product_section_contract,
    recommendation_reorder_contract,
    recommendation_search_recovery_contract,
)
from shopfront.searching.contracts import search_query_contract, search_suggestions_contract

from .serializers import (
    RecommendationResponseSerializer,
    RecommendationSeedRequestSerializer,
    SearchQueryResponseSerializer,
    SearchSuggestionsResponseSerializer,
)


def _limit(value: object, *, default: int, upper: int, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(upper, parsed))


def _user_id(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _status_from_payload(payload: dict[str, object]) -> int:
    if payload.get("ok"):
        return status.HTTP_200_OK
    if payload.get("error") == "authentication_required":
        return status.HTTP_401_UNAUTHORIZED
    if payload.get("error") == "product_not_found":
        return status.HTTP_404_NOT_FOUND
    return status.HTTP_400_BAD_REQUEST


class InternalTokenRequiredAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def _check_internal_token(self, request) -> Response | None:
        expected = str(getattr(settings, "INTERNAL_TOKEN", "") or "")
        actual = str(request.headers.get("X-Internal-Token") or "")
        if not expected or not actual or actual != expected:
            return Response({"detail": "forbidden"}, status=status.HTTP_403_FORBIDDEN)
        return None


class InternalSearchQueryAPIView(InternalTokenRequiredAPIView):
    @extend_schema(exclude=True)
    def get(self, request):
        forbidden = self._check_internal_token(request)
        if forbidden is not None:
            return forbidden
        payload = search_query_contract(
            query=str(request.query_params.get("q") or "").strip(),
            limit=_limit(request.query_params.get("limit"), default=24, upper=64),
            country_limit=_limit(request.query_params.get("country_limit"), default=6, upper=24, minimum=0),
            request=request,
            mode_override="django-inline",
        )
        serializer = SearchQueryResponseSerializer(payload)
        return Response(serializer.data)


class InternalSearchSuggestionsAPIView(InternalTokenRequiredAPIView):
    @extend_schema(exclude=True)
    def get(self, request):
        forbidden = self._check_internal_token(request)
        if forbidden is not None:
            return forbidden
        payload = search_suggestions_contract(
            query=str(request.query_params.get("q") or "").strip(),
            limit=_limit(request.query_params.get("limit"), default=10, upper=32),
            country_limit=_limit(request.query_params.get("country_limit"), default=6, upper=24, minimum=0),
            request=request,
            mode_override="django-inline",
        )
        serializer = SearchSuggestionsResponseSerializer(payload)
        return Response(serializer.data)


class InternalRecommendationHomeAPIView(InternalTokenRequiredAPIView):
    @extend_schema(exclude=True)
    def get(self, request):
        forbidden = self._check_internal_token(request)
        if forbidden is not None:
            return forbidden
        payload = recommendation_home_contract(
            request=request,
            limit=_limit(request.query_params.get("limit"), default=8, upper=32),
            mode_override="django-inline",
            user_id_override=_user_id(request.query_params.get("user_id")),
        )
        serializer = RecommendationResponseSerializer(payload)
        return Response(serializer.data, status=_status_from_payload(payload))


class InternalRecommendationProductAPIView(InternalTokenRequiredAPIView):
    @extend_schema(exclude=True)
    def get(self, request, product_id: int):
        forbidden = self._check_internal_token(request)
        if forbidden is not None:
            return forbidden
        payload = recommendation_product_contract(
            request=request,
            product_id=product_id,
            limit=_limit(request.query_params.get("limit"), default=12, upper=32),
            mode_override="django-inline",
            user_id_override=_user_id(request.query_params.get("user_id")),
        )
        serializer = RecommendationResponseSerializer(payload)
        return Response(serializer.data, status=_status_from_payload(payload))


class InternalRecommendationProductSectionAPIView(InternalTokenRequiredAPIView):
    @extend_schema(exclude=True)
    def get(self, request, product_id: int, section: str):
        forbidden = self._check_internal_token(request)
        if forbidden is not None:
            return forbidden
        payload = recommendation_product_section_contract(
            request=request,
            product_id=product_id,
            section=section,
            mode_override="django-inline",
            user_id_override=_user_id(request.query_params.get("user_id")),
        )
        serializer = RecommendationResponseSerializer(payload)
        return Response(serializer.data, status=_status_from_payload(payload))


class InternalRecommendationCartAPIView(InternalTokenRequiredAPIView):
    @extend_schema(exclude=True)
    def post(self, request):
        forbidden = self._check_internal_token(request)
        if forbidden is not None:
            return forbidden
        request_serializer = RecommendationSeedRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        payload = recommendation_cart_contract(
            request=request,
            product_ids=request_serializer.validated_data["product_ids"],
            limit=int(request_serializer.validated_data.get("limit", 8)),
            checkout=False,
            mode_override="django-inline",
            user_id_override=_user_id(request.data.get("user_id")),
        )
        serializer = RecommendationResponseSerializer(payload)
        return Response(serializer.data, status=_status_from_payload(payload))


class InternalRecommendationCheckoutAPIView(InternalTokenRequiredAPIView):
    @extend_schema(exclude=True)
    def post(self, request):
        forbidden = self._check_internal_token(request)
        if forbidden is not None:
            return forbidden
        request_serializer = RecommendationSeedRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        payload = recommendation_cart_contract(
            request=request,
            product_ids=request_serializer.validated_data["product_ids"],
            limit=int(request_serializer.validated_data.get("limit", 6)),
            checkout=True,
            mode_override="django-inline",
            user_id_override=_user_id(request.data.get("user_id")),
        )
        serializer = RecommendationResponseSerializer(payload)
        return Response(serializer.data, status=_status_from_payload(payload))


class InternalRecommendationReorderAPIView(InternalTokenRequiredAPIView):
    @extend_schema(exclude=True)
    def get(self, request):
        forbidden = self._check_internal_token(request)
        if forbidden is not None:
            return forbidden
        payload = recommendation_reorder_contract(
            request=request,
            limit=_limit(request.query_params.get("limit"), default=8, upper=32),
            mode_override="django-inline",
            user_id_override=_user_id(request.query_params.get("user_id")),
        )
        serializer = RecommendationResponseSerializer(payload)
        return Response(serializer.data, status=_status_from_payload(payload))


class InternalRecommendationSearchRecoveryAPIView(InternalTokenRequiredAPIView):
    @extend_schema(exclude=True)
    def get(self, request):
        forbidden = self._check_internal_token(request)
        if forbidden is not None:
            return forbidden
        payload = recommendation_search_recovery_contract(
            request=request,
            query=str(request.query_params.get("q") or "").strip(),
            limit=_limit(request.query_params.get("limit"), default=8, upper=32),
            mode_override="django-inline",
            user_id_override=_user_id(request.query_params.get("user_id")),
        )
        serializer = RecommendationResponseSerializer(payload)
        return Response(serializer.data, status=_status_from_payload(payload))

