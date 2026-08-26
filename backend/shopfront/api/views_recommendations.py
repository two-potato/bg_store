from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
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

from .serializers import RecommendationResponseSerializer, RecommendationSeedRequestSerializer


def _limit(value: object, *, default: int, upper: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(upper, parsed))


def _status_from_payload(payload: dict[str, object]) -> int:
    if payload.get("ok"):
        return status.HTTP_200_OK
    if payload.get("error") == "authentication_required":
        return status.HTTP_401_UNAUTHORIZED
    if payload.get("error") == "product_not_found":
        return status.HTTP_404_NOT_FOUND
    return status.HTTP_400_BAD_REQUEST


class RecommendationHomeAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Recommendations"],
        summary="Home recommendations contract",
        description="Единый контракт home recommendation surfaces с fallback на Django-движок.",
        parameters=[OpenApiParameter("limit", int, OpenApiParameter.QUERY, required=False, description="Лимит в секции (1..32)")],
        responses={200: OpenApiResponse(response=RecommendationResponseSerializer)},
    )
    def get(self, request):
        payload = recommendation_home_contract(request=request, limit=_limit(request.query_params.get("limit"), default=8, upper=32))
        serializer = RecommendationResponseSerializer(payload)
        return Response(serializer.data, status=_status_from_payload(payload))


class RecommendationProductAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Recommendations"],
        summary="Product recommendations contract",
        description="Контракт рекомендаций PDP (similar/accessories/substitutes) для выбранного product.",
        parameters=[OpenApiParameter("limit", int, OpenApiParameter.QUERY, required=False, description="Лимит в секции (1..32)")],
        responses={200: OpenApiResponse(response=RecommendationResponseSerializer)},
    )
    def get(self, request, product_id: int):
        payload = recommendation_product_contract(
            request=request,
            product_id=product_id,
            limit=_limit(request.query_params.get("limit"), default=12, upper=32),
        )
        serializer = RecommendationResponseSerializer(payload)
        return Response(serializer.data, status=_status_from_payload(payload))


class RecommendationProductSectionAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Recommendations"],
        summary="Product recommendation section contract",
        description="Контракт для отдельной секции PDP recommendations (`fbt`, `alternatives`, `seller_more`).",
        responses={200: OpenApiResponse(response=RecommendationResponseSerializer)},
    )
    def get(self, request, product_id: int, section: str):
        payload = recommendation_product_section_contract(request=request, product_id=product_id, section=section)
        serializer = RecommendationResponseSerializer(payload)
        return Response(serializer.data, status=_status_from_payload(payload))


class RecommendationCartAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Recommendations"],
        summary="Cart recommendations contract",
        description="Контракт cross-sell для корзины.",
        request=RecommendationSeedRequestSerializer,
        responses={200: OpenApiResponse(response=RecommendationResponseSerializer)},
    )
    def post(self, request):
        request_serializer = RecommendationSeedRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        payload = recommendation_cart_contract(
            request=request,
            product_ids=request_serializer.validated_data["product_ids"],
            limit=int(request_serializer.validated_data.get("limit", 8)),
            checkout=False,
        )
        serializer = RecommendationResponseSerializer(payload)
        return Response(serializer.data, status=_status_from_payload(payload))


class RecommendationCheckoutAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Recommendations"],
        summary="Checkout recommendations contract",
        description="Контракт cross-sell для checkout.",
        request=RecommendationSeedRequestSerializer,
        responses={200: OpenApiResponse(response=RecommendationResponseSerializer)},
    )
    def post(self, request):
        request_serializer = RecommendationSeedRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        payload = recommendation_cart_contract(
            request=request,
            product_ids=request_serializer.validated_data["product_ids"],
            limit=int(request_serializer.validated_data.get("limit", 6)),
            checkout=True,
        )
        serializer = RecommendationResponseSerializer(payload)
        return Response(serializer.data, status=_status_from_payload(payload))


class RecommendationReorderAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Recommendations"],
        summary="Reorder recommendations contract",
        description="Персональные рекомендации для повторного заказа (требует auth).",
        parameters=[OpenApiParameter("limit", int, OpenApiParameter.QUERY, required=False, description="Лимит в секции (1..32)")],
        responses={
            200: OpenApiResponse(response=RecommendationResponseSerializer),
            401: OpenApiResponse(description="Пользователь не аутентифицирован"),
        },
    )
    def get(self, request):
        payload = recommendation_reorder_contract(request=request, limit=_limit(request.query_params.get("limit"), default=8, upper=32))
        serializer = RecommendationResponseSerializer(payload)
        return Response(serializer.data, status=_status_from_payload(payload))


class RecommendationSearchRecoveryAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Recommendations"],
        summary="Search recovery recommendations contract",
        description="Рекомендации на zero-result search для recovery surfaces.",
        parameters=[
            OpenApiParameter("q", str, OpenApiParameter.QUERY, required=True, description="Исходный поисковый запрос"),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY, required=False, description="Лимит в секции (1..32)"),
        ],
        responses={200: OpenApiResponse(response=RecommendationResponseSerializer)},
    )
    def get(self, request):
        query = str(request.query_params.get("q") or "").strip()
        payload = recommendation_search_recovery_contract(
            request=request,
            query=query,
            limit=_limit(request.query_params.get("limit"), default=8, upper=32),
        )
        serializer = RecommendationResponseSerializer(payload)
        return Response(serializer.data, status=_status_from_payload(payload))
