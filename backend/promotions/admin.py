from django.contrib import admin

from .models import Coupon, PromotionRedemption, PromotionRule


@admin.register(PromotionRule)
class PromotionRuleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "discount_type", "discount_value", "customer_scope", "is_active", "stack_with_profile_discount")
    list_filter = ("discount_type", "customer_scope", "is_active", "stack_with_profile_discount")
    search_fields = ("name", "description")


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "rule", "is_active", "usage_limit", "per_user_limit", "created_at")
    list_filter = ("is_active", "rule__discount_type")
    search_fields = ("code", "rule__name")


@admin.register(PromotionRedemption)
class PromotionRedemptionAdmin(admin.ModelAdmin):
    list_display = ("id", "coupon", "order", "redeemed_by", "guest_email", "discount_amount", "created_at")
    list_filter = ("coupon",)
    search_fields = ("coupon__code", "order__id", "guest_email", "redeemed_by__username")
