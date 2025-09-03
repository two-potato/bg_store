from django.contrib import admin
from django_fsm import can_proceed
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("name", "price", "qty")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "legal_entity", "placed_by", "total", "created_at")
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

    actions = ["approve_order", "reject_order"]

    def approve_order(self, request, queryset):
        for order in queryset:
            if can_proceed(order.approve):
                order.approve()
                order.save()

    approve_order.short_description = "Approve selected orders"

    def reject_order(self, request, queryset):
        for order in queryset:
            if can_proceed(order.cancel):
                order.cancel()
                order.save()

    reject_order.short_description = "Reject selected orders"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product", "name", "price", "qty")
    list_filter = ("order",)
