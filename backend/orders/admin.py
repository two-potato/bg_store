from django import forms
from django.contrib import admin
from django.http import HttpResponse
import csv
import logging
from .models import Order, OrderItem, FakeAcquiringPayment, OrderSellerSplit, SellerOrder, SellerOrderItem, Shipment, ShipmentItem, OrderApprovalLog
from .services import plan_seller_splits, mark_seller_order_status


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("name", "price", "qty")


class FakeAcquiringPaymentInline(admin.StackedInline):
    model = FakeAcquiringPayment
    extra = 0
    can_delete = False
    readonly_fields = ("provider_payment_id", "status", "last_event", "amount", "history", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("provider_payment_id", "status", "last_event", "amount")}),
        ("История событий", {"fields": ("history",)}),
        ("Служебные", {"fields": ("created_at", "updated_at")}),
    )


class OrderSellerSplitInline(admin.TabularInline):
    model = OrderSellerSplit
    extra = 0
    readonly_fields = ("seller", "seller_store_name", "items_count", "subtotal", "status", "created_at")
    can_delete = False


class SellerOrderInline(admin.TabularInline):
    model = SellerOrder
    extra = 0
    readonly_fields = ("seller", "seller_store_name", "status", "subtotal", "total", "accepted_at", "shipped_at", "delivered_at")
    can_delete = False


class OrderApprovalLogInline(admin.TabularInline):
    model = OrderApprovalLog
    extra = 0
    readonly_fields = ("actor", "decision", "comment", "created_at")
    can_delete = False


class OrderAdminForm(forms.ModelForm):
    status = forms.ChoiceField(
        choices=(
            (Order.Status.NEW, "Новый"),
            (Order.Status.DELIVERING, "В работе"),
            (Order.Status.DELIVERED, "Выполнен"),
        )
    )

    class Meta:
        model = Order
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            current = self.instance.status
            if current not in {Order.Status.NEW, Order.Status.DELIVERING, Order.Status.DELIVERED}:
                # Legacy statuses are treated as "in progress" in admin UI.
                current = Order.Status.DELIVERING
            self.fields["status"].initial = current


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    form = OrderAdminForm
    list_display = ("id", "status_label", "approval_status", "split_status", "legal_entity", "placed_by", "coupon_code", "total", "created_at")
    list_filter = ("status", "approval_status", "split_status", "legal_entity", "source_channel")
    search_fields = ("id", "placed_by__username", "coupon_code", "customer_comment")
    inlines = [OrderItemInline, OrderSellerSplitInline, SellerOrderInline, OrderApprovalLogInline, FakeAcquiringPaymentInline]
    readonly_fields = (
        "subtotal",
        "discount_amount",
        "total",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (None, {
            "fields": (
                "status",
                "customer_type", "payment_method",
                "legal_entity", "placed_by", "delivery_address",
                "customer_name", "customer_phone", "address_text",
                "customer_comment", "coupon_code", "source_channel", "split_status",
                "approval_status", "requested_by", "approved_by", "approved_at",
            )
        }),
        ("Суммы", {"fields": ("subtotal", "discount_amount", "total")}),
        ("Служебные", {"fields": ("created_at", "updated_at")}),
    )

    actions = [
        "mark_new",
        "mark_in_progress",
        "mark_completed",
        "sync_split_structure",
        "export_selected_rows",
    ]

    def mark_new(self, request, queryset):
        log = logging.getLogger("orders")
        for order in queryset:
            order.status = Order.Status.NEW
            order.save(update_fields=["status", "updated_at"])
            log.info("order_marked_new", extra={"order_id": order.id})
    mark_new.short_description = "Отметить как новые"

    def mark_in_progress(self, request, queryset):
        log = logging.getLogger("orders")
        for order in queryset:
            # Admin shortcut: direct set to "in progress".
            order.status = Order.Status.DELIVERING
            order.save(update_fields=["status", "updated_at"])
            log.info("order_marked_in_progress", extra={"order_id": order.id})
    mark_in_progress.short_description = "Перевести в работу"

    def mark_completed(self, request, queryset):
        log = logging.getLogger("orders")
        for order in queryset:
            # Admin shortcut: direct set to "completed".
            order.status = Order.Status.DELIVERED
            order.save(update_fields=["status", "updated_at"])
            log.info("order_marked_completed", extra={"order_id": order.id})
    mark_completed.short_description = "Отметить как выполненные"

    def status_label(self, obj):
        return obj.get_status_display()
    status_label.short_description = "Статус"

    @admin.action(description="Синхронизировать split-структуру")
    def sync_split_structure(self, request, queryset):
        for order in queryset:
            plan_seller_splits(order)

    @admin.action(description="Экспортировать заказы в CSV")
    def export_selected_rows(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="orders-export.csv"'
        writer = csv.writer(response)
        writer.writerow(["id", "status", "split_status", "placed_by", "total", "created_at"])
        for order in queryset:
            writer.writerow([order.id, order.status, order.split_status, order.placed_by_id, order.total, order.created_at])
        return response

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product", "name", "price", "qty")
    list_filter = ("order",)


@admin.register(FakeAcquiringPayment)
class FakeAcquiringPaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "provider_payment_id", "status", "last_event", "amount", "updated_at")
    search_fields = ("provider_payment_id", "order__id", "order__placed_by__username")
    list_filter = ("status", "last_event")
    readonly_fields = ("history", "created_at", "updated_at")


@admin.register(OrderSellerSplit)
class OrderSellerSplitAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "seller", "seller_store_name", "items_count", "subtotal", "status", "created_at")
    search_fields = ("order__id", "seller__username", "seller_store_name")
    list_filter = ("status",)


class SellerOrderItemInline(admin.TabularInline):
    model = SellerOrderItem
    extra = 0
    readonly_fields = ("order_item", "product", "seller_offer", "name", "price", "qty")
    can_delete = False


class ShipmentInline(admin.TabularInline):
    model = Shipment
    extra = 0
    readonly_fields = ("tracking_number", "delivery_method", "warehouse_name", "status", "packed_at", "shipped_at", "delivered_at")
    can_delete = False


@admin.register(SellerOrder)
class SellerOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "seller", "seller_store_name", "status", "subtotal", "total", "created_at")
    search_fields = ("order__id", "seller__username", "seller_store_name", "customer_comment")
    list_filter = ("status",)
    inlines = [SellerOrderItemInline, ShipmentInline]
    actions = ("mark_accepted", "mark_shipped", "mark_delivered")

    @admin.action(description="Отметить seller order как accepted")
    def mark_accepted(self, request, queryset):
        for seller_order in queryset:
            mark_seller_order_status(seller_order, SellerOrder.Status.ACCEPTED)

    @admin.action(description="Отметить seller order как shipped")
    def mark_shipped(self, request, queryset):
        for seller_order in queryset:
            mark_seller_order_status(seller_order, SellerOrder.Status.SHIPPED)

    @admin.action(description="Отметить seller order как delivered")
    def mark_delivered(self, request, queryset):
        for seller_order in queryset:
            mark_seller_order_status(seller_order, SellerOrder.Status.DELIVERED)


class ShipmentItemInline(admin.TabularInline):
    model = ShipmentItem
    extra = 0


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ("id", "seller_order", "tracking_number", "delivery_method", "warehouse_name", "status", "created_at")
    search_fields = ("tracking_number", "seller_order__order__id", "warehouse_name")
    list_filter = ("status", "delivery_method")
    inlines = [ShipmentItemInline]


@admin.register(OrderApprovalLog)
class OrderApprovalLogAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "actor", "decision", "created_at")
    search_fields = ("order__id", "actor__username", "comment")
    list_filter = ("decision",)
