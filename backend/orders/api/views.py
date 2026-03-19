from rest_framework import viewsets, mixins, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from django.conf import settings
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
import hmac
from ..models import Order, OrderItem, OrderSellerSplit, SellerOrder, SellerOrderItem, Shipment
from ..serializers import OrderSerializer, OrderCreateSerializer
from commerce.serializers import SimpleOkSerializer, DetailSerializer, ValidationErrorSerializer
from commerce.models import LegalEntityMembership
from core.logging_utils import LoggedViewSetMixin, LoggedAPIViewMixin
import logging

log = logging.getLogger("orders")


def _order_api_queryset():
    return (
        Order.objects.all()
        .select_related("legal_entity", "delivery_address", "placed_by")
        .prefetch_related(
            Prefetch("items", queryset=OrderItem.objects.select_related("product", "seller_offer")),
            Prefetch("seller_splits", queryset=OrderSellerSplit.objects.select_related("seller")),
            Prefetch(
                "seller_orders",
                queryset=SellerOrder.objects.select_related("seller").prefetch_related(
                    Prefetch("items", queryset=SellerOrderItem.objects.select_related("product", "seller_offer")),
                    Prefetch("shipments", queryset=Shipment.objects.prefetch_related("items")),
                ),
            ),
        )
    )

@extend_schema_view(
    list=extend_schema(
        tags=["Orders"],
        summary="List company orders",
        description="Возвращает заказы текущего пользователя по юрлицам, где он состоит участником.",
        responses={
            200: OrderSerializer(many=True),
            401: OpenApiResponse(response=DetailSerializer, description="Пользователь не аутентифицирован"),
        },
    ),
    retrieve=extend_schema(
        tags=["Orders"],
        summary="Retrieve order",
        description="Возвращает полный заказ вместе с позициями, seller splits и seller orders.",
        responses={
            200: OrderSerializer,
            401: OpenApiResponse(response=DetailSerializer, description="Пользователь не аутентифицирован"),
            404: OpenApiResponse(response=DetailSerializer, description="Заказ не найден или недоступен пользователю"),
        },
    ),
    create=extend_schema(
        tags=["Orders"],
        summary="Create order",
        description="Создаёт новый заказ компании, рассчитывает скидку, approval status и seller splits.",
        request=OrderCreateSerializer,
        responses={
            201: OrderSerializer,
            400: OpenApiResponse(response=ValidationErrorSerializer, description="Ошибка валидации или бизнес-правил"),
            401: OpenApiResponse(response=DetailSerializer, description="Пользователь не аутентифицирован"),
        },
        examples=[
            OpenApiExample(
                "Create order request",
                value={
                    "legal_entity_id": 7,
                    "delivery_address_id": 14,
                    "customer_comment": "Нужна утренняя доставка.",
                    "coupon_code": "WELCOME10",
                    "items": [
                        {"product_id": 101, "qty": 2},
                        {"product_id": 205, "qty": 1},
                    ],
                },
                request_only=True,
            )
        ],
    ),
)
class OrderViewSet(LoggedViewSetMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = _order_api_queryset()

    def get_queryset(self):
        return self.queryset.filter(legal_entity__members=self.request.user)

    def get_serializer_class(self):
        return OrderCreateSerializer if self.action == "create" else OrderSerializer

    def create(self, request, *a, **kw):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        order = ser.save()
        log.info("order_created_api", extra={"order_id": order.id, "user_id": request.user.id})
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

class IsInternalService(permissions.BasePermission):
    def has_permission(self, request, view):
        expected = (getattr(settings, "INTERNAL_TOKEN", "") or "").strip()
        provided = (request.headers.get("X-Internal-Token") or "").strip()
        if not expected or expected in {"change-me", "dev", "dev-secret"}:
            return False
        return hmac.compare_digest(provided, expected)

@extend_schema(
    tags=["Internal Orders"],
    summary="Approve order",
    description="Внутренний endpoint для approve заказа. Требует `X-Internal-Token` и `X-Admin-Telegram-Id`.",
    parameters=[
        OpenApiParameter(name="X-Internal-Token", type=str, location=OpenApiParameter.HEADER, required=True),
        OpenApiParameter(name="X-Admin-Telegram-Id", type=int, location=OpenApiParameter.HEADER, required=True),
    ],
    request=None,
    responses={
        200: SimpleOkSerializer,
        403: OpenApiResponse(response=DetailSerializer, description="Неверный internal token или пользователь не является админом юрлица"),
        404: OpenApiResponse(response=DetailSerializer, description="Заказ не найден"),
    },
)
class OrderApproveView(LoggedAPIViewMixin, APIView):
    permission_classes = [IsInternalService]
    serializer_class = SimpleOkSerializer

    def post(self, request, pk):
        admin_tg_id = int(request.headers.get("X-Admin-Telegram-Id","0") or 0)
        order = get_object_or_404(Order.objects.select_related("legal_entity"), pk=pk)
        if not LegalEntityMembership.objects.filter(
            legal_entity=order.legal_entity, user__profile__telegram_id=admin_tg_id,
            role__code__in=["owner","admin"]
        ).exists():
            log.warning("order_approve_forbidden_not_entity_admin", extra={"order_id": order.id, "admin_tg_id": admin_tg_id, "legal_entity_id": order.legal_entity_id})
            return Response({"detail":"Not entity admin"}, status=403)
        order.approve()
        order.approval_status = Order.ApprovalStatus.APPROVED
        order.save(update_fields=["status", "approval_status"])
        log.info("order_approved", extra={"order_id": order.id, "admin_tg_id": admin_tg_id})
        return Response({"ok": True})

@extend_schema(
    tags=["Internal Orders"],
    summary="Reject order",
    description="Внутренний endpoint для reject заказа. Требует `X-Internal-Token` и `X-Admin-Telegram-Id`.",
    parameters=[
        OpenApiParameter(name="X-Internal-Token", type=str, location=OpenApiParameter.HEADER, required=True),
        OpenApiParameter(name="X-Admin-Telegram-Id", type=int, location=OpenApiParameter.HEADER, required=True),
    ],
    request=None,
    responses={
        200: SimpleOkSerializer,
        403: OpenApiResponse(response=DetailSerializer, description="Неверный internal token или пользователь не является админом юрлица"),
        404: OpenApiResponse(response=DetailSerializer, description="Заказ не найден"),
    },
)
class OrderRejectView(LoggedAPIViewMixin, APIView):
    permission_classes = [IsInternalService]
    serializer_class = SimpleOkSerializer

    def post(self, request, pk):
        admin_tg_id = int(request.headers.get("X-Admin-Telegram-Id","0") or 0)
        order = get_object_or_404(Order.objects.select_related("legal_entity","placed_by__profile"), pk=pk)
        if not LegalEntityMembership.objects.filter(
            legal_entity=order.legal_entity, user__profile__telegram_id=admin_tg_id,
            role__code__in=["owner","admin"]
        ).exists():
            log.warning("order_reject_forbidden_not_entity_admin", extra={"order_id": order.id, "admin_tg_id": admin_tg_id, "legal_entity_id": order.legal_entity_id})
            return Response({"detail":"Not entity admin"}, status=403)
        order.cancel()
        order.approval_status = Order.ApprovalStatus.REJECTED
        order.save(update_fields=["status", "approval_status"])
        log.info("order_rejected", extra={"order_id": order.id, "admin_tg_id": admin_tg_id})
        return Response({"ok": True})
