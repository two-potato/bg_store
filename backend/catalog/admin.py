from django.contrib import admin
from django.db.models import Avg, Count
from .models import (
    Brand, Series, Category, Product, ProductImage, Tag, Color, Country,
    ProductReview, ProductReviewComment,
)

admin.site.register(Brand)
admin.site.register(Series)
admin.site.register(Category)
admin.site.register(Tag)
admin.site.register(Color)
admin.site.register(Country)
admin.site.register(ProductReview)
admin.site.register(ProductReviewComment)

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


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "id", "sku", "name", "brand", "series", "category",
        "rating_avg_display", "rating_count_display",
        "price", "stock_qty", "flavor", "is_new", "is_promo",
    )
    search_fields = ("sku","name","manufacturer_sku")
    list_filter = ("brand","series","category","is_new","is_promo","tags")
    inlines = [ProductImageInline, ProductReviewInline]

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
