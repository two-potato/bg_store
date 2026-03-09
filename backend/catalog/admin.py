import csv
from django.http import HttpResponse
from django.contrib import admin
from django.db.models import Avg, Count
from .models import (
    Brand, Series, Category, Product, ProductImage, ProductDocument, Collection, CollectionItem,
    Tag, Color, Country, ProductReview, ProductReviewComment, ProductReviewPhoto, ProductReviewVote, ProductQuestion,
    SellerOffer, SellerInventory,
)

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "created_at")
    search_fields = ("name", "slug", "description", "landing_body")


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ("id", "brand", "name")
    search_fields = ("name", "brand__name")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "parent")
    search_fields = ("name", "slug", "description", "landing_body")
admin.site.register(Tag)
admin.site.register(Color)
admin.site.register(Country)
admin.site.register(ProductReview)
admin.site.register(ProductReviewComment)
admin.site.register(ProductReviewPhoto)
admin.site.register(ProductReviewVote)
admin.site.register(ProductQuestion)


class CollectionItemInline(admin.TabularInline):
    model = CollectionItem
    extra = 1


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "is_active", "is_featured")
    search_fields = ("name", "slug", "description")
    list_filter = ("is_active", "is_featured")
    inlines = [CollectionItemInline]

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductReviewInline(admin.TabularInline):
    model = ProductReview
    extra = 0
    fields = ("user", "rating", "text", "created_at")
    readonly_fields = ("user", "rating", "text", "created_at")
    can_delete = False
    max_num = 0
    verbose_name = "Отзыв"
    verbose_name_plural = "Отзывы и рейтинги"


class ProductDocumentInline(admin.TabularInline):
    model = ProductDocument
    extra = 0


def _export_queryset_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{modeladmin.model._meta.model_name}-export.csv"'
    writer = csv.writer(response)
    field_names = [field.name for field in modeladmin.model._meta.fields]
    writer.writerow(field_names)
    for obj in queryset:
        writer.writerow([getattr(obj, name) for name in field_names])
    return response


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "id", "sku", "name", "seller", "brand", "series", "category",
        "rating_avg_display", "rating_count_display",
        "price", "stock_qty", "flavor", "is_new", "is_promo",
    )
    search_fields = ("sku","name","manufacturer_sku")
    list_filter = ("brand","series","category","is_new","is_promo","tags")
    inlines = [ProductImageInline, ProductDocumentInline, ProductReviewInline]
    actions = ("export_selected_rows",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_rating_avg=Avg("reviews__rating"), _rating_count=Count("reviews"))

    @admin.display(description="Рейтинг", ordering="_rating_avg")
    def rating_avg_display(self, obj):
        if obj._rating_avg is None:
            return "—"
        return f"{obj._rating_avg:.1f}"

    @admin.display(description="Отзывов", ordering="_rating_count")
    def rating_count_display(self, obj):
        return obj._rating_count

    @admin.action(description="Экспортировать товары в CSV")
    def export_selected_rows(self, request, queryset):
        return _export_queryset_csv(self, request, queryset)


@admin.register(ProductDocument)
class ProductDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "title", "kind", "ordering", "created_at")
    search_fields = ("title", "product__name", "product__sku")
    list_filter = ("kind", "created_at")
    actions = ("export_selected_rows",)

    @admin.action(description="Экспортировать документы в CSV")
    def export_selected_rows(self, request, queryset):
        return _export_queryset_csv(self, request, queryset)


class SellerInventoryInline(admin.TabularInline):
    model = SellerInventory
    extra = 0


@admin.register(SellerOffer)
class SellerOfferAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "seller", "seller_store", "price", "status", "min_order_qty", "lead_time_days", "is_featured")
    search_fields = ("product__name", "product__sku", "seller__username", "seller_store__name")
    list_filter = ("status", "is_featured", "seller_store")
    inlines = [SellerInventoryInline]
    actions = ("export_selected_rows",)

    @admin.action(description="Экспортировать офферы в CSV")
    def export_selected_rows(self, request, queryset):
        return _export_queryset_csv(self, request, queryset)


@admin.register(SellerInventory)
class SellerInventoryAdmin(admin.ModelAdmin):
    list_display = ("id", "offer", "warehouse_name", "stock_qty", "reserved_qty", "incoming_qty", "eta_days", "is_primary")
    search_fields = ("offer__product__name", "offer__product__sku", "warehouse_name", "warehouse_code")
    list_filter = ("is_primary",)
    actions = ("export_selected_rows",)

    @admin.action(description="Экспортировать остатки в CSV")
    def export_selected_rows(self, request, queryset):
        return _export_queryset_csv(self, request, queryset)
