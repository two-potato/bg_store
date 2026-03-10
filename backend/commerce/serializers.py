from rest_framework import serializers
from .models import DeliveryAddress, MembershipRequest, LegalEntityCreationRequest


class CheckInnResponseSerializer(serializers.Serializer):
    exists = serializers.BooleanField()
    legal_entity_id = serializers.IntegerField(required=False)
    name = serializers.CharField(required=False)


class CheckInnRequestSerializer(serializers.Serializer):
    inn = serializers.CharField()


class MembershipRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipRequest
        fields = ["id","legal_entity","comment"]

    def create(self, validated_data):
        validated_data["applicant"] = self.context["request"].user
        return super().create(validated_data)


class LegalEntityCreationRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalEntityCreationRequest
        fields = ["id","name","inn","bik","checking_account","bank_name"]

    def create(self, validated_data):
        validated_data["applicant"] = self.context["request"].user
        return super().create(validated_data)


class DeliveryAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryAddress
        fields = [
            "id","label","country","city","street","postcode","details",
            "latitude","longitude","is_default","legal_entity"
        ]
        read_only_fields = ["legal_entity"]


class SimpleOkSerializer(serializers.Serializer):
    ok = serializers.BooleanField()


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


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


class LookupBankResponseSerializer(serializers.Serializer):
    bik = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)
    correspondent_account = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)


class ReverseGeocodeResponseSerializer(serializers.Serializer):
    country = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)
    street = serializers.CharField(required=False, allow_blank=True)
    postcode = serializers.CharField(required=False, allow_blank=True)
    house = serializers.CharField(required=False, allow_blank=True)
    lat = serializers.FloatField(required=False)
    lon = serializers.FloatField(required=False)
