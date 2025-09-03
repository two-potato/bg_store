from django.contrib import admin
from .models import User, UserProfile

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id","username","email","is_staff","is_active")
    search_fields = ("username","email")

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user","telegram_id","telegram_username","discount")
    search_fields = ("telegram_id","telegram_username","user__username")
