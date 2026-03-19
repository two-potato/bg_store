from rest_framework import serializers
from drf_spectacular.utils import OpenApiExample, extend_schema_serializer
from .models import DeliveryAddress, MembershipRequest, LegalEntityCreationRequest


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "INN check response",
            value={"exists": True, "legal_entity_id": 7, "name": "Complaex Bar LLC"},
            response_only=True,
        )
    ]
)
class CheckInnResponseSerializer(serializers.Serializer):
    exists = serializers.BooleanField()
    legal_entity_id = serializers.IntegerField(required=False)
    name = serializers.CharField(required=False)


@extend_schema_serializer(
    examples=[OpenApiExample("INN check request", value={"inn": "7707083893"}, request_only=True)]
)
class CheckInnRequestSerializer(serializers.Serializer):
    inn = serializers.CharField(help_text="ИНН юридического лица или ИП")


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Membership request",
            value={"id": 12, "legal_entity": 7, "comment": "Подключите доступ закупщику бара"},
            request_only=True,
        )
    ]
)
class MembershipRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipRequest
        fields = ["id","legal_entity","comment"]
        extra_kwargs = {
            "legal_entity": {"help_text": "ID юридического лица, к которому запрашивается доступ"},
            "comment": {"help_text": "Комментарий к заявке на вступление"},
        }

    def create(self, validated_data):
        validated_data["applicant"] = self.context["request"].user
        return super().create(validated_data)


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Legal entity create request",
            value={
                "id": 4,
                "name": "Complaex Bar LLC",
                "inn": "7707083893",
                "bik": "044525225",
                "checking_account": "40702810900000000001",
                "bank_name": "AO TBank",
            },
            request_only=True,
        )
    ]
)
class LegalEntityCreationRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalEntityCreationRequest
        fields = ["id","name","inn","bik","checking_account","bank_name"]
        extra_kwargs = {
            "name": {"help_text": "Официальное наименование компании"},
            "inn": {"help_text": "ИНН компании"},
            "bik": {"help_text": "БИК банка"},
            "checking_account": {"help_text": "Расчётный счёт компании"},
            "bank_name": {"help_text": "Название обслуживающего банка"},
        }

    def create(self, validated_data):
        validated_data["applicant"] = self.context["request"].user
        return super().create(validated_data)


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Delivery address",
            value={
                "id": 14,
                "label": "Основной склад",
                "country": "Россия",
                "city": "Москва",
                "street": "Ленинградский проспект, 37",
                "postcode": "125167",
                "details": "Подъезд 2, звонок охране",
                "latitude": 55.790278,
                "longitude": 37.544444,
                "is_default": True,
                "legal_entity": 7,
            },
            response_only=True,
        )
    ]
)
class DeliveryAddressSerializer(serializers.ModelSerializer):
    label = serializers.CharField(help_text="Короткое имя адреса, видимое пользователю")
    country = serializers.CharField(help_text="Страна доставки")
    city = serializers.CharField(help_text="Город доставки")
    street = serializers.CharField(help_text="Улица, дом, корпус")
    postcode = serializers.CharField(required=False, allow_blank=True, help_text="Почтовый индекс")
    details = serializers.CharField(required=False, allow_blank=True, help_text="Комментарий для курьера")
    latitude = serializers.FloatField(required=False, allow_null=True, help_text="Широта точки доставки")
    longitude = serializers.FloatField(required=False, allow_null=True, help_text="Долгота точки доставки")
    is_default = serializers.BooleanField(required=False, help_text="Является ли адрес адресом по умолчанию")

    class Meta:
        model = DeliveryAddress
        fields = [
            "id","label","country","city","street","postcode","details",
            "latitude","longitude","is_default","legal_entity"
        ]
        read_only_fields = ["legal_entity"]


@extend_schema_serializer(
    examples=[OpenApiExample("Simple OK", value={"ok": True}, response_only=True)]
)
class SimpleOkSerializer(serializers.Serializer):
    ok = serializers.BooleanField()


@extend_schema_serializer(
    examples=[OpenApiExample("Approval result", value={"ok": True, "legal_entity_id": 7}, response_only=True)]
)
class SimpleOkWithLegalEntitySerializer(SimpleOkSerializer):
    legal_entity_id = serializers.IntegerField()


@extend_schema_serializer(
    examples=[OpenApiExample("Detail", value={"detail": "Недостаточно прав"}, response_only=True)]
)
class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Validation error",
            value={"items": ["This field is required."], "non_field_errors": ["Некоторые товары не найдены."]},
            response_only=True,
        )
    ]
)
class ValidationErrorSerializer(serializers.Serializer):
    non_field_errors = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Ошибки, не привязанные к конкретному полю",
    )
    items = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Ошибки в поле `items` или других полях запроса",
    )


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Party lookup response",
            value={
                "inn": "7707083893",
                "kpp": "773601001",
                "ogrn": "1027700132195",
                "name": "ООО Комплаекс Бар",
                "address": "г Москва, Ленинградский пр-кт, д 37",
                "street": "Ленинградский проспект",
                "house": "37",
                "block": "",
                "building": "",
                "management": "Иванов Иван Иванович",
                "okved": "56.10",
                "status": "ACTIVE",
            },
            response_only=True,
        )
    ]
)
class LookupPartyResponseSerializer(serializers.Serializer):
    inn = serializers.CharField(required=False, allow_blank=True)
    kpp = serializers.CharField(required=False, allow_blank=True)
    ogrn = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    street = serializers.CharField(required=False, allow_blank=True)
    house = serializers.CharField(required=False, allow_blank=True)
    block = serializers.CharField(required=False, allow_blank=True)
    building = serializers.CharField(required=False, allow_blank=True)
    management = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    okved = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    status = serializers.CharField(required=False, allow_blank=True, allow_null=True)


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Bank lookup response",
            value={
                "bik": "044525225",
                "name": "АО ТБАНК",
                "correspondent_account": "30101810145250000225",
                "address": "127287, г Москва, ул Хуторская 2-я, д 38А стр 26",
            },
            response_only=True,
        )
    ]
)
class LookupBankResponseSerializer(serializers.Serializer):
    bik = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)
    correspondent_account = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Reverse geocode response",
            value={
                "country": "Россия",
                "city": "Москва",
                "street": "Ленинградский проспект",
                "postcode": "125167",
                "house": "37",
                "lat": 55.790278,
                "lon": 37.544444,
            },
            response_only=True,
        )
    ]
)
class ReverseGeocodeResponseSerializer(serializers.Serializer):
    country = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)
    street = serializers.CharField(required=False, allow_blank=True)
    postcode = serializers.CharField(required=False, allow_blank=True)
    house = serializers.CharField(required=False, allow_blank=True)
    lat = serializers.FloatField(required=False)
    lon = serializers.FloatField(required=False)
