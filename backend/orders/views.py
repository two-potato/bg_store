from rest_framework import viewsets, mixins, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
from django.shortcuts import get_object_or_404
import hmac
from .models import Order
from .serializers import OrderSerializer, OrderCreateSerializer
from commerce.models import LegalEntityMembership
from core.logging_utils import LoggedViewSetMixin, LoggedAPIViewMixin
import logging

log = logging.getLogger("orders")

class OrderViewSet(LoggedViewSetMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = (
        Order.objects.all()
        .select_related("legal_entity", "delivery_address", "placed_by")
        .prefetch_related("items", "items__product")
    )

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

class OrderApproveView(LoggedAPIViewMixin, APIView):
    permission_classes = [IsInternalService]
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
        order.save(update_fields=["status"])
        log.info("order_approved", extra={"order_id": order.id, "admin_tg_id": admin_tg_id})
        return Response({"ok": True})

class OrderRejectView(LoggedAPIViewMixin, APIView):
    permission_classes = [IsInternalService]
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
        order.save(update_fields=["status"])
        log.info("order_rejected", extra={"order_id": order.id, "admin_tg_id": admin_tg_id})
        return Response({"ok": True})
