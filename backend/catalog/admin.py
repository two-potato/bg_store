from django.contrib import admin
from .models import Brand, Series, Category, Product, ProductImage, Tag

admin.site.register(Brand)
admin.site.register(Series)
admin.site.register(Category)
admin.site.register(Tag)

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id","sku","name","brand","series","category","price","stock_qty","flavor","is_new","is_promo")
    search_fields = ("sku","name","manufacturer_sku")
    list_filter = ("brand","series","category","is_new","is_promo","tags")
    inlines = [ProductImageInline]
