from django.contrib import admin
from .models import IdempotencyKey

@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ("user_id","route","key","expires_at")
    search_fields = ("user_id","route","key")
