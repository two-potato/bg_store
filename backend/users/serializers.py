from rest_framework import serializers
from drf_spectacular.utils import OpenApiExample, extend_schema_serializer
from .models import UserProfile


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "User profile",
            value={"telegram_id": 123456789, "telegram_username": "complaex_owner", "discount": "7.50"},
            response_only=True,
        )
    ]
)
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["telegram_id","telegram_username","discount"]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Current user",
            value={
                "username": "horeca_manager",
                "telegram_id": 123456789,
                "discount": "7.50",
                "role": "buyer",
                "seller_store": None,
            },
            response_only=True,
        )
    ]
)
class MeSerializer(serializers.Serializer):
    username = serializers.CharField(help_text="Логин текущего пользователя")
    telegram_id = serializers.IntegerField(allow_null=True, help_text="Telegram ID, если профиль привязан")
    discount = serializers.CharField(help_text="Текущая персональная скидка")
    role = serializers.ChoiceField(
        choices=UserProfile.Role.choices,
        allow_null=True,
        help_text="Роль пользователя в системе: admin, manager, client, seller",
    )
    seller_store = serializers.CharField(allow_null=True, help_text="Название магазина продавца, если применимо")


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Telegram auth request",
            value={"initData": "query_id=AAE...&user=%7B%22id%22%3A123456789%7D&hash=..."},
            request_only=True,
        )
    ]
)
class TelegramWebAppAuthRequestSerializer(serializers.Serializer):
    initData = serializers.CharField(help_text="Строка initData, полученная из Telegram Web App")


@extend_schema_serializer(
    examples=[OpenApiExample("JWT response", value={"access": "eyJhbGciOi..."}, response_only=True)]
)
class TelegramWebAppAuthResponseSerializer(serializers.Serializer):
    access = serializers.CharField()


@extend_schema_serializer(
    examples=[OpenApiExample("User detail", value={"detail": "Authentication credentials were not provided."}, response_only=True)]
)
class UserDetailSerializer(serializers.Serializer):
    detail = serializers.CharField()
