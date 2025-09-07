from django.contrib import admin
from .models import User, UserProfile, Friendship

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id","username","email","is_staff","is_active")
    search_fields = ("username","email")

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user","telegram_id","telegram_username","discount")
    search_fields = ("telegram_id","telegram_username","user__username")

@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ("from_user", "to_user", "accepted", "created_at", "updated_at")
    list_filter = ("accepted",)
    search_fields = ("from_user__username", "to_user__username")
