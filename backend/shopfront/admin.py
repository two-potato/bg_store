from django.contrib import admin

from .models import (
    FavoriteProduct,
    SavedSearch,
    PersistentCart,
    CategorySubscription,
    BrandSubscription,
    RecentlyViewedProduct,
    RecommendationEvent,
    RecommendationPopularitySnapshot,
    RecommendationProductAffinity,
    RecommendationReplenishmentProfile,
    RecommendationSet,
    RecommendationUserAffinity,
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


@admin.register(RecommendationEvent)
class RecommendationEventAdmin(admin.ModelAdmin):
    list_display = ("id", "event", "surface", "recommendation_source", "product", "user", "created_at")
    list_filter = ("event", "surface", "recommendation_source")
    search_fields = ("product__name", "product__sku", "user__username", "request_id", "session_key")
    readonly_fields = ("created_at", "updated_at")


@admin.register(RecommendationProductAffinity)
class RecommendationProductAffinityAdmin(admin.ModelAdmin):
    list_display = ("id", "source_product", "target_product", "affinity_type", "score", "orders_count", "updated_at")
    list_filter = ("affinity_type",)
    search_fields = ("source_product__name", "source_product__sku", "target_product__name", "target_product__sku")


@admin.register(RecommendationPopularitySnapshot)
class RecommendationPopularitySnapshotAdmin(admin.ModelAdmin):
    list_display = ("id", "scope_type", "scope_id", "window", "product", "score", "updated_at")
    list_filter = ("scope_type", "window")
    search_fields = ("product__name", "product__sku")


@admin.register(RecommendationSet)
class RecommendationSetAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "scope_type", "scope_id", "source", "generated_at", "expires_at")
    list_filter = ("kind", "scope_type", "source")
    search_fields = ("kind", "source")
    readonly_fields = ("created_at", "updated_at", "generated_at")


@admin.register(RecommendationUserAffinity)
class RecommendationUserAffinityAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "dimension", "entity_id", "entity_key", "score", "event_count", "updated_at")
    list_filter = ("dimension",)
    search_fields = ("user__username", "entity_key")
    readonly_fields = ("created_at", "updated_at")


@admin.register(RecommendationReplenishmentProfile)
class RecommendationReplenishmentProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "product", "orders_count", "quantity_total", "expected_interval_days", "score", "last_ordered_at")
    search_fields = ("user__username", "product__name", "product__sku")
    readonly_fields = ("created_at", "updated_at")
