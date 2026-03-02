from django import forms
from django.contrib import admin
import logging
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("name", "price", "qty")


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
    list_display = ("id", "status_label", "legal_entity", "placed_by", "total", "created_at")
    list_filter = ("status", "legal_entity")
    search_fields = ("id", "placed_by__username")
    inlines = [OrderItemInline]
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
            )
        }),
        ("Суммы", {"fields": ("subtotal", "discount_amount", "total")}),
        ("Служебные", {"fields": ("created_at", "updated_at")}),
    )

    actions = [
        "mark_new",
        "mark_in_progress",
        "mark_completed",
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

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product", "name", "price", "qty")
    list_filter = ("order",)
