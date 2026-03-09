from rest_framework import viewsets, mixins, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from django.conf import settings
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
import hmac
from .models import Order, OrderItem, OrderSellerSplit, SellerOrder, SellerOrderItem, Shipment
from .serializers import OrderSerializer, OrderCreateSerializer
from commerce.serializers import SimpleOkSerializer, DetailSerializer
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

@extend_schema(request=None, responses={200: SimpleOkSerializer, 403: DetailSerializer})
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

@extend_schema(request=None, responses={200: SimpleOkSerializer, 403: DetailSerializer})
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
