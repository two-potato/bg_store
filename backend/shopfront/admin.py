from django.contrib import admin

from .models import (
    FavoriteProduct,
    SavedSearch,
    PersistentCart,
    CategorySubscription,
    BrandSubscription,
    RecentlyViewedProduct,
    SavedList,
    SavedListItem,
)


@admin.register(FavoriteProduct)
class FavoriteProductAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "product", "created_at")
    search_fields = ("user__username", "product__name", "product__sku")


@admin.register(SavedSearch)
class SavedSearchAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name", "created_at")
    search_fields = ("user__username", "name", "querystring")


@admin.register(PersistentCart)
class PersistentCartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "updated_at")
    search_fields = ("user__username",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(CategorySubscription)
class CategorySubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "category", "created_at")
    search_fields = ("user__username", "category__name", "category__slug")


@admin.register(BrandSubscription)
class BrandSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "brand", "created_at")
    search_fields = ("user__username", "brand__name")


@admin.register(RecentlyViewedProduct)
class RecentlyViewedProductAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "product", "updated_at")
    search_fields = ("user__username", "product__name", "product__sku")


class SavedListItemInline(admin.TabularInline):
    model = SavedListItem
    extra = 0


@admin.register(SavedList)
class SavedListAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name", "source", "is_public", "updated_at")
    search_fields = ("user__username", "name", "description", "share_token")
    list_filter = ("source", "is_public")
    inlines = [SavedListItemInline]
