from rest_framework import serializers
from .models import UserProfile
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["telegram_id","telegram_username","discount"]
