from __future__ import annotations

from catalog.models import Product
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .gateway import call


def _limit(value: object, *, default: int, upper: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(upper, parsed))


def _product_ids(data) -> list[int]:
    result: list[int] = []
    values = data.get("product_ids") if isinstance(data, dict) else []
    for raw in values or []:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            result.append(value)
    return result


def _product_missing(product_id: int) -> Response | None:
    if Product.objects.filter(pk=product_id).exists():
        return None
    return Response(
        {"ok": False, "surface": "pdp", "variant": "control", "sections": [], "error": "product_not_found"},
        status=status.HTTP_404_NOT_FOUND,
    )


class RecommendationHomeAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        limit = _limit(request.query_params.get("limit"), default=8, upper=32)
        return Response(call("/v1/recommendations/home", request=request, surface="home", limit=limit))


class RecommendationProductAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, product_id: int):
        missing = _product_missing(product_id)
        if missing is not None:
            return missing
        limit = _limit(request.query_params.get("limit"), default=12, upper=32)
        return Response(call(f"/v1/recommendations/product/{product_id}", request=request, surface="pdp", limit=limit))


class RecommendationProductSectionAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, product_id: int, section: str):
        missing = _product_missing(product_id)
        if missing is not None:
            return missing
        return Response(call(f"/v1/recommendations/product/{product_id}/section/{section}", request=request, surface="pdp", limit=8))


class RecommendationCartAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        product_ids = _product_ids(request.data)
        limit = _limit(request.data.get("limit") if isinstance(request.data, dict) else None, default=8, upper=32)
        return Response(call("/v1/recommendations/cart", request=request, surface="cart", limit=limit, method="POST", body={"product_ids": product_ids}))


class RecommendationCheckoutAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        product_ids = _product_ids(request.data)
        limit = _limit(request.data.get("limit") if isinstance(request.data, dict) else None, default=6, upper=32)
        return Response(call("/v1/recommendations/checkout", request=request, surface="checkout", limit=limit, method="POST", body={"product_ids": product_ids}))


class RecommendationReorderAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        limit = _limit(request.query_params.get("limit"), default=8, upper=32)
        return Response(call("/v1/recommendations/reorder", request=request, surface="reorder", limit=limit))


class RecommendationSearchRecoveryAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        query = str(request.query_params.get("q") or "").strip()
        limit = _limit(request.query_params.get("limit"), default=8, upper=32)
        return Response(call("/v1/recommendations/search-recovery", request=request, surface="catalog", limit=limit, extra_params={"q": query}))
