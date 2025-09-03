from rest_framework import viewsets, mixins, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.conf import settings
from django.shortcuts import get_object_or_404
from .models import Order
from .serializers import OrderSerializer, OrderCreateSerializer
from .tasks import notify_entity_admins_order_created, send_invoice_to_buyer
from commerce.models import LegalEntityMembership
from core.logging_utils import LoggedViewSetMixin, LoggedAPIViewMixin

class OrderViewSet(LoggedViewSetMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Order.objects.all().select_related("legal_entity","delivery_address","placed_by").prefetch_related("items")

    def get_queryset(self):
        return Order.objects.filter(legal_entity__members=self.request.user)

    def get_serializer_class(self):
        return OrderCreateSerializer if self.action == "create" else OrderSerializer

    def create(self, request, *a, **kw):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        order = ser.save()
        transaction.on_commit(lambda: notify_entity_admins_order_created.delay(order.id))
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

class IsInternalService(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.headers.get("X-Internal-Token") == settings.INTERNAL_TOKEN

class OrderApproveView(LoggedAPIViewMixin, APIView):
    permission_classes = [IsInternalService]
    def post(self, request, pk):
        admin_tg_id = int(request.headers.get("X-Admin-Telegram-Id","0") or 0)
        order = get_object_or_404(Order.objects.select_related("legal_entity"), pk=pk)
        if not LegalEntityMembership.objects.filter(
            legal_entity=order.legal_entity, user__profile__telegram_id=admin_tg_id,
            role__in=[LegalEntityMembership.Role.OWNER, LegalEntityMembership.Role.ADMIN]
        ).exists():
            return Response({"detail":"Not entity admin"}, status=403)
        order.approve()
        order.save(update_fields=["status"])
        transaction.on_commit(lambda: send_invoice_to_buyer.delay(order.id))
        return Response({"ok": True})

class OrderRejectView(LoggedAPIViewMixin, APIView):
    permission_classes = [IsInternalService]
    def post(self, request, pk):
        admin_tg_id = int(request.headers.get("X-Admin-Telegram-Id","0") or 0)
        order = get_object_or_404(Order.objects.select_related("legal_entity","placed_by__profile"), pk=pk)
        if not LegalEntityMembership.objects.filter(
            legal_entity=order.legal_entity, user__profile__telegram_id=admin_tg_id,
            role__in=[LegalEntityMembership.Role.OWNER, LegalEntityMembership.Role.ADMIN]
        ).exists():
            return Response({"detail":"Not entity admin"}, status=403)
        order.cancel()
        order.save(update_fields=["status"])
        return Response({"ok": True})
