from rest_framework import serializers
from .models import UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["telegram_id","telegram_username","discount"]


class MeSerializer(serializers.Serializer):
    username = serializers.CharField()
    telegram_id = serializers.IntegerField(allow_null=True)
    discount = serializers.CharField()
    role = serializers.CharField(allow_null=True)
    seller_store = serializers.CharField(allow_null=True)


class TelegramWebAppAuthRequestSerializer(serializers.Serializer):
    initData = serializers.CharField()


class TelegramWebAppAuthResponseSerializer(serializers.Serializer):
    access = serializers.CharField()


class UserDetailSerializer(serializers.Serializer):
    detail = serializers.CharField()
