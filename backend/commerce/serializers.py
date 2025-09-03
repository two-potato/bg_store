from rest_framework import serializers
from .models import DeliveryAddress, MembershipRequest, LegalEntityCreationRequest

class CheckInnResponseSerializer(serializers.Serializer):
    exists = serializers.BooleanField()
    legal_entity_id = serializers.IntegerField(required=False)
    name = serializers.CharField(required=False)

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
